"""Orders, payment confirmation and tickets (04 §6, R5/R6).

Create: every seat must still be held by the caller (Redis) and unsold (Postgres); the total is
computed here from `price_tiers` + the flat fee, never taken from the client; the gateway order
is created; the price per seat is frozen in `order_seats`.

Confirm (`verify` fast path, webhook, demo pay — all the same function, all idempotent through
`orders.status` under a row lock): insert one ticket per seat. `UNIQUE (showtime_id, seat_id)`
is the final guard — if the hold lapsed and someone else bought a seat meanwhile, the insert
fails, the payment is refunded and the order is `refunded` with `refund_reason = seat_sold`. If
the hold lapsed but the seats are still free, the sale simply goes through (paid after expiry).

Pending orders older than 15 minutes read as `expired` (no cron).
"""

from __future__ import annotations

import logging
import secrets
import uuid
from datetime import datetime, timedelta

from redis.asyncio import Redis
from sqlalchemy import insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.errors import ApiError
from app.models import Event, Order, OrderSeat, PriceTier, Seat, Showtime, Ticket, User, Venue
from app.models.enums import OrderStatus
from app.schemas.orders import (
    Customer,
    MyTickets,
    OrderEvent,
    OrderSeatOut,
    OrderShowtime,
    OrderVenue,
    TicketBundle,
    TicketGroup,
    TicketOut,
)
from app.schemas.orders import Order as OrderOut
from app.services import holds
from app.services import tickets as tokens
from app.services.payments import Gateway
from app.services.showtimes import FEE_PAISE, _check_seats, _load, _sold

log = logging.getLogger(__name__)

PAY_WINDOW = timedelta(minutes=15)
SEAT_SOLD = "seat_sold"


def seat_label(template: str, section_label: str, row: str, n: int) -> str:
    """ "G9"; in an arena every wedge has its own row A, so "Section 3 · C7" / "Floor · C7"."""
    return f"{section_label} · {row}{n}" if template == "arena" else f"{row}{n}"


def _bad_id(raw: str) -> uuid.UUID:
    try:
        return uuid.UUID(raw)
    except ValueError as e:
        raise ApiError("not_found", "No such order") from e


# --- create ---------------------------------------------------------------------------------------


async def create(
    db: AsyncSession,
    redis: Redis,
    gateway: Gateway,
    *,
    user: User,
    holder: str,
    showtime_id: uuid.UUID,
    seat_ids: list[str],
    now: datetime,
) -> Order:
    showtime, _, venue = await _load(db, str(showtime_id), now)
    ids = await _check_seats(db, showtime, venue, seat_ids)

    # Idempotent: Proceed pressed twice (or a refresh) returns the same pending order.
    for existing in await db.scalars(
        select(Order).where(
            Order.user_id == user.id,
            Order.showtime_id == showtime.id,
            Order.status == OrderStatus.PENDING,
            Order.created_at > now - PAY_WINDOW,
        )
    ):
        seats = set(
            str(s)
            for s in await db.scalars(
                select(OrderSeat.seat_id).where(OrderSeat.order_id == existing.id)
            )
        )
        if seats == set(ids):
            return existing

    mine, _ = await holds.owned(redis, showtime.id, holder, ids)
    missing = [s for s in ids if s not in set(mine)]
    if missing:
        raise ApiError(
            "hold_missing",
            "Your hold on these seats has lapsed. Pick them again on the map.",
            status=409,
            details={"missing": missing},
        )
    sold = set(await _sold(db, showtime.id)) & set(ids)
    if sold:
        raise ApiError(
            "seat_taken", "Some of these seats were just sold", status=409,
            details={"taken": sorted(sold)},
        )  # fmt: skip

    tiers = {
        t.tier_key: t
        for t in await db.scalars(select(PriceTier).where(PriceTier.showtime_id == showtime.id))
    }
    seat_rows = list(await db.scalars(select(Seat).where(Seat.id.in_([uuid.UUID(i) for i in ids]))))
    subtotal = sum(tiers[s.tier_key].price_paise for s in seat_rows)
    fee = FEE_PAISE * len(seat_rows)
    order = Order(
        user_id=user.id,
        sid=holder,
        showtime_id=showtime.id,
        status=OrderStatus.PENDING,
        subtotal_paise=subtotal,
        fee_paise=fee,
        total_paise=subtotal + fee,
    )
    db.add(order)
    await db.flush()
    db.add_all(
        OrderSeat(
            order_id=order.id,
            seat_id=s.id,
            tier_key=s.tier_key,
            price_paise=tiers[s.tier_key].price_paise,
        )
        for s in seat_rows
    )
    order.razorpay_order_id = await gateway.create_order(order.total_paise, receipt=str(order.id))
    await db.commit()
    return order


# --- read -----------------------------------------------------------------------------------------


async def expire_if_stale(db: AsyncSession, order: Order, now: datetime) -> None:
    if order.status == OrderStatus.PENDING and order.created_at + PAY_WINDOW <= now:
        order.status = OrderStatus.EXPIRED
        await db.commit()


async def owned_order(db: AsyncSession, order_id: str, user: User, now: datetime) -> Order:
    """The caller's order, or 404 — someone else's order doesn't exist for them."""
    order = await db.get(Order, _bad_id(order_id))
    if order is None or order.user_id != user.id:
        raise ApiError("not_found", "No such order")
    await expire_if_stale(db, order, now)
    return order


async def _showtime_out(db: AsyncSession, showtime_id: uuid.UUID) -> tuple[OrderShowtime, Venue]:
    row = (
        await db.execute(
            select(Showtime, Event, Venue)
            .join(Event, Event.id == Showtime.event_id)
            .join(Venue, Venue.id == Showtime.venue_id)
            .where(Showtime.id == showtime_id)
        )
    ).one()
    showtime, event, venue = row._tuple()
    return (
        OrderShowtime(
            id=showtime.id,
            starts_at=showtime.starts_at,
            ends_at=showtime.starts_at + timedelta(minutes=event.duration_min),
            event=OrderEvent(
                slug=event.slug,
                title=event.title,
                type=event.type.value,  # type: ignore[arg-type]
                poster_url=event.poster_url,
                duration_min=event.duration_min,
                rating=event.rating,
            ),
            venue=OrderVenue(id=venue.id, name=venue.name, address=venue.address),
        ),
        venue,
    )


def _labels(venue: Venue) -> tuple[dict[str, str], dict[str, str]]:
    """section key → label, tier key → label, from the stored layout."""
    sections = {s["key"]: s["label"] for s in venue.layout["sections"]}
    tiers = {t["key"]: t["label"] for t in venue.layout["tiers"]}
    return sections, tiers


async def _seats_out(db: AsyncSession, order: Order, venue: Venue) -> list[OrderSeatOut]:
    sections, tier_labels = _labels(venue)
    tier_names = {
        t.tier_key: t.label
        for t in await db.scalars(
            select(PriceTier).where(PriceTier.showtime_id == order.showtime_id)
        )
    }
    rows = (
        await db.execute(
            select(OrderSeat, Seat)
            .join(Seat, Seat.id == OrderSeat.seat_id)
            .where(OrderSeat.order_id == order.id)
            .order_by(Seat.section_key, Seat.row_label, Seat.number)
        )
    ).all()
    return [
        OrderSeatOut(
            seat_id=str(seat.id),
            label=seat_label(
                venue.template.value,
                sections.get(seat.section_key, ""),
                seat.row_label,
                seat.number,
            ),
            tier_key=os.tier_key,
            tier_label=tier_names.get(os.tier_key) or tier_labels.get(os.tier_key, os.tier_key),
            price_paise=os.price_paise,
        )  # fmt: skip
        for os, seat in (r._tuple() for r in rows)
    ]


async def view(
    db: AsyncSession,
    order: Order,
    gateway: Gateway,
    *,
    user: User,
    redis: Redis | None,
) -> OrderOut:
    showtime, venue = await _showtime_out(db, order.showtime_id)
    seats = await _seats_out(db, order, venue)
    hold_expires_at = None
    if order.status == OrderStatus.PENDING and redis is not None:
        try:
            _, hold_expires_at = await holds.owned(
                redis, order.showtime_id, order.sid, [s.seat_id for s in seats]
            )
        except ApiError:
            hold_expires_at = None
    return OrderOut(
        id=order.id,
        status=order.status.value,  # type: ignore[arg-type]
        showtime=showtime,
        seats=seats,
        subtotal_paise=order.subtotal_paise,
        fee_paise=order.fee_paise,
        total_paise=order.total_paise,
        created_at=order.created_at,
        paid_at=order.paid_at,
        pay_by=order.created_at + PAY_WINDOW,
        hold_expires_at=hold_expires_at,
        refund_reason=order.refund_reason,
        gateway=gateway.mode,
        razorpay_order_id=order.razorpay_order_id,
        key_id=gateway.key_id,
        customer=Customer(name=user.name, email=user.email),
    )


# --- confirm --------------------------------------------------------------------------------------


async def confirm(
    db: AsyncSession,
    redis: Redis | None,
    gateway: Gateway,
    order_id: uuid.UUID,
    *,
    payment_id: str,
    now: datetime,
) -> Order:
    """Turn a captured payment into tickets — or a refund when a seat went to someone else.
    Safe to call any number of times, from any path, concurrently."""
    order = await db.scalar(select(Order).where(Order.id == order_id).with_for_update())
    if order is None:
        raise ApiError("not_found", "No such order")
    if order.status in (OrderStatus.PAID, OrderStatus.REFUNDED):
        await db.commit()  # release the row lock
        return order

    seats = list(await db.scalars(select(OrderSeat).where(OrderSeat.order_id == order.id)))
    rows = [
        {
            "id": uuid.uuid4(),
            "order_id": order.id,
            "showtime_id": order.showtime_id,
            "seat_id": s.seat_id,
            "user_id": order.user_id,
        }
        for s in seats
    ]
    order.razorpay_payment_id = payment_id
    try:
        async with db.begin_nested():
            await db.execute(insert(Ticket), rows)
    except IntegrityError:
        # A seat was sold to someone else after this hold lapsed: refund the whole payment.
        order.status = OrderStatus.REFUNDED
        order.refund_reason = SEAT_SOLD
        order.refund_id = await gateway.refund(payment_id, order.total_paise)
        await db.commit()
        log.info("order %s refunded: seat sold after the hold lapsed", order.id)
        return order

    order.status = OrderStatus.PAID
    order.paid_at = now
    await db.commit()
    await holds.clear_sold(redis, order.showtime_id, [str(s.seat_id) for s in seats])
    return order


async def mark_failed(db: AsyncSession, razorpay_order_id: str) -> None:
    order = await db.scalar(
        select(Order).where(Order.razorpay_order_id == razorpay_order_id).with_for_update()
    )
    if order is not None and order.status == OrderStatus.PENDING:
        order.status = OrderStatus.FAILED
    await db.commit()


def demo_payment_id() -> str:
    return f"pay_demo_{secrets.token_hex(7)}"


# --- tickets --------------------------------------------------------------------------------------


async def ticket_bundle(
    db: AsyncSession,
    settings: Settings,
    gateway: Gateway,
    order_id: str,
    *,
    user: User,
    now: datetime,
) -> TicketBundle:
    order = await owned_order(db, order_id, user, now)
    if order.status != OrderStatus.PAID:
        raise ApiError("not_found", "No tickets for this order")
    out = await view(db, order, gateway, user=user, redis=None)
    labels = {s.seat_id: s for s in out.seats}
    exp = tokens.expiry_for(out.showtime.ends_at)
    tickets = sorted(
        await db.scalars(select(Ticket).where(Ticket.order_id == order.id)),
        key=lambda t: list(labels).index(str(t.seat_id)),
    )
    return TicketBundle(
        order=out,
        tickets=[
            TicketOut(
                id=t.id,
                seat_id=str(t.seat_id),
                label=labels[str(t.seat_id)].label,
                tier_label=labels[str(t.seat_id)].tier_label,
                qr_token=tokens.sign(settings, t.id, t.showtime_id, exp),
                checked_in_at=t.checked_in_at,
            )
            for t in tickets
        ],
    )


async def my_tickets(db: AsyncSession, user: User, *, now: datetime) -> MyTickets:
    orders = list(
        await db.scalars(
            select(Order).where(Order.user_id == user.id, Order.status == OrderStatus.PAID)
        )
    )
    groups: list[TicketGroup] = []
    venues: dict[uuid.UUID, tuple[OrderShowtime, Venue]] = {}
    for order in orders:
        if order.showtime_id not in venues:
            venues[order.showtime_id] = await _showtime_out(db, order.showtime_id)
        showtime, venue = venues[order.showtime_id]
        seats = await _seats_out(db, order, venue)
        groups.append(
            TicketGroup(
                order_id=order.id,
                showtime=showtime,
                seats=[s.label for s in seats],
                tier_labels=list(dict.fromkeys(s.tier_label for s in seats)),
                total_paise=order.total_paise,
                paid_at=order.paid_at,
            )
        )
    upcoming = sorted((g for g in groups if g.showtime.ends_at > now), key=_when)
    past = sorted((g for g in groups if g.showtime.ends_at <= now), key=_when, reverse=True)
    return MyTickets(upcoming=upcoming, past=past)


def _when(g: TicketGroup) -> datetime:
    return g.showtime.starts_at
