"""Orders, payment confirmation and tickets (04 §6, R6/R7).

Create: every seat must still be held by the caller (Redis) and unsold (Postgres); the total is
computed here from `show_prices` + the flat fee, never taken from the client; the gateway order
is created; the price per seat is frozen in `order_seats`.

Confirm (`verify` fast path, webhook, demo pay — all the same function, all idempotent through
`orders.status` under a row lock): insert one ticket per seat. `UNIQUE (show_id, seat_id)` is
the final guard — if the hold lapsed and someone else bought a seat meanwhile, the insert fails,
the payment is refunded and the order is `refunded` with `refund_reason = seat_sold`. If the
hold lapsed but the seats are still free, the sale simply goes through (paid after expiry).
A refund the gateway didn't take leaves `refund_id` empty ("refund in progress") and is retried
whenever the order is read or confirmed again (no cron).

Pending orders older than 15 minutes read as `expired` (no cron).
"""

from __future__ import annotations

import logging
import secrets
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta

from redis.asyncio import Redis
from sqlalchemy import func, insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.errors import ApiError
from app.models import Cinema, Film, Order, OrderSeat, Screen, Seat, Show, ShowPrice, Ticket, User
from app.models.enums import OrderStatus
from app.schemas.orders import (
    Customer,
    MyTickets,
    OrderCinema,
    OrderFilm,
    OrderSeatOut,
    OrderShow,
    TicketBundle,
    TicketGroup,
    TicketOut,
)
from app.schemas.orders import Order as OrderOut
from app.services import holds
from app.services import tickets as tokens
from app.services.payments import Gateway
from app.services.schedules import FEE_PAISE
from app.services.shows import check_seats, load, parse_id, sold_seats

log = logging.getLogger(__name__)

PAY_WINDOW = timedelta(minutes=15)
SEAT_SOLD = "seat_sold"

OnPaid = Callable[[Order], Awaitable[None]]


def seat_label(row: str, n: int) -> str:
    """ "G9" — row letters run on from the stalls into the balcony, so they're unique."""
    return f"{row}{n}"


# --- create ---------------------------------------------------------------------------------------


async def create(
    db: AsyncSession,
    redis: Redis,
    gateway: Gateway,
    *,
    user: User,
    holder: str,
    show_id: uuid.UUID,
    seat_ids: list[str],
    now: datetime,
) -> Order:
    show, _, _, _ = await load(db, show_id, now)
    ids = await check_seats(db, show, seat_ids)

    # Idempotent: Proceed pressed twice (or a refresh) returns the same pending order. The lock
    # on the user makes a double-submit wait for the first to commit, then find its order.
    await db.execute(select(User.id).where(User.id == user.id).with_for_update())
    for existing in await db.scalars(
        select(Order).where(
            Order.user_id == user.id,
            Order.show_id == show.id,
            Order.status == OrderStatus.PENDING,
            Order.created_at > now - PAY_WINDOW,
        )
    ):
        seats = {
            str(s)
            for s in await db.scalars(
                select(OrderSeat.seat_id).where(OrderSeat.order_id == existing.id)
            )
        }
        if seats == set(ids):
            return existing

    mine, _ = await holds.owned(redis, show.id, holder, ids)
    missing = [s for s in ids if s not in set(mine)]
    if missing:
        raise ApiError(
            "hold_missing",
            "Your hold on these seats has lapsed. Pick them again on the map.",
            status=409,
            details={"missing": missing},
        )
    sold = set(await sold_seats(db, show.id)) & set(ids)
    if sold:
        raise ApiError(
            "seat_taken", "Some of these seats were just sold", status=409,
            details={"taken": sorted(sold)},
        )  # fmt: skip

    prices = {
        p.tier_key: p.price_paise
        for p in await db.scalars(select(ShowPrice).where(ShowPrice.show_id == show.id))
    }
    seat_rows = list(await db.scalars(select(Seat).where(Seat.id.in_([uuid.UUID(i) for i in ids]))))
    subtotal = sum(prices[s.tier_key] for s in seat_rows)
    fee = FEE_PAISE * len(seat_rows)
    order = Order(
        user_id=user.id,
        sid=holder,
        show_id=show.id,
        status=OrderStatus.PENDING,
        subtotal_paise=subtotal,
        fee_paise=fee,
        total_paise=subtotal + fee,
    )
    db.add(order)
    await db.flush()
    db.add_all(
        OrderSeat(
            order_id=order.id, seat_id=s.id, tier_key=s.tier_key, price_paise=prices[s.tier_key]
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
    order = await db.get(Order, parse_id(order_id, "order"))
    if order is None or order.user_id != user.id:
        raise ApiError("not_found", "No such order")
    await expire_if_stale(db, order, now)
    return order


async def show_out(db: AsyncSession, show_id: uuid.UUID) -> tuple[OrderShow, Screen]:
    row = (
        await db.execute(
            select(Show, Film, Screen, Cinema)
            .join(Film, Film.id == Show.film_id)
            .join(Screen, Screen.id == Show.screen_id)
            .join(Cinema, Cinema.id == Screen.cinema_id)
            .where(Show.id == show_id)
        )
    ).one()
    show, film, screen, cinema = row._tuple()
    return (
        OrderShow(
            id=show.id,
            starts_at=show.starts_at,
            ends_at=show.ends_at,
            language=show.language,
            format=show.format,
            screen_name=screen.name,
            film=OrderFilm(
                slug=film.slug,
                title=film.title,
                cert=film.cert.value if film.cert else None,  # type: ignore[arg-type]
                poster_url=film.poster_url,
                runtime_min=film.runtime_min,
            ),
            cinema=OrderCinema(
                id=cinema.id, name=cinema.name, area=cinema.area, address=cinema.address
            ),
        ),
        screen,
    )


async def seats_out(db: AsyncSession, order: Order, screen: Screen) -> list[OrderSeatOut]:
    tier_labels = {t["key"]: t["label"] for t in screen.tiers}
    rows = (
        await db.execute(
            select(OrderSeat, Seat)
            .join(Seat, Seat.id == OrderSeat.seat_id)
            .where(OrderSeat.order_id == order.id)
            .order_by(Seat.row_label, Seat.number)
        )
    ).all()
    return [
        OrderSeatOut(
            seat_id=str(seat.id),
            label=seat_label(seat.row_label, seat.number),
            tier_key=os.tier_key,
            tier_label=tier_labels.get(os.tier_key, os.tier_key),
            price_paise=os.price_paise,
        )
        for os, seat in (r._tuple() for r in rows)
    ]


async def settle_refund(db: AsyncSession, gateway: Gateway, order: Order) -> None:
    """Retry a refund the gateway didn't take the first time."""
    if (
        order.status == OrderStatus.REFUNDED
        and order.refund_id is None
        and order.razorpay_payment_id
    ):
        order.refund_id = await gateway.refund(order.razorpay_payment_id, order.total_paise)
        if order.refund_id:
            await db.commit()


async def view(
    db: AsyncSession,
    order: Order,
    gateway: Gateway,
    *,
    user: User,
    redis: Redis | None,
) -> OrderOut:
    await settle_refund(db, gateway, order)
    show, screen = await show_out(db, order.show_id)
    seats = await seats_out(db, order, screen)
    hold_expires_at = None
    if order.status == OrderStatus.PENDING and redis is not None:
        try:
            _, hold_expires_at = await holds.owned(
                redis, order.show_id, order.sid, [s.seat_id for s in seats]
            )
        except ApiError:
            hold_expires_at = None
    return OrderOut(
        id=order.id,
        status=order.status.value,  # type: ignore[arg-type]
        show=show,
        seats=seats,
        subtotal_paise=order.subtotal_paise,
        fee_paise=order.fee_paise,
        total_paise=order.total_paise,
        created_at=order.created_at,
        paid_at=order.paid_at,
        payment_method=order.payment_method,
        pay_by=order.created_at + PAY_WINDOW,
        hold_expires_at=hold_expires_at,
        refund_reason=order.refund_reason,
        refund_pending=order.status == OrderStatus.REFUNDED and order.refund_id is None,
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
    method: str | None = None,
    on_paid: OnPaid | None = None,
) -> Order:
    """Turn a captured payment into tickets — or a refund when a seat went to someone else.
    Safe to call any number of times, from any path, concurrently. `on_paid` runs once, after
    the commit, on the call that actually sold the seats (the ticket email)."""
    order = await db.scalar(select(Order).where(Order.id == order_id).with_for_update())
    if order is None:
        raise ApiError("not_found", "No such order")
    if order.status in (OrderStatus.PAID, OrderStatus.REFUNDED):
        await settle_refund(db, gateway, order)
        await db.commit()  # release the row lock
        return order

    seats = list(await db.scalars(select(OrderSeat).where(OrderSeat.order_id == order.id)))
    rows = [
        {
            "id": uuid.uuid4(),
            "order_id": order.id,
            "show_id": order.show_id,
            "seat_id": s.seat_id,
            "user_id": order.user_id,
        }
        for s in seats
    ]
    order.razorpay_payment_id = payment_id
    order.payment_method = method or ("Test payment" if gateway.mode == "demo" else "Razorpay")
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
    await holds.clear_sold(redis, order.show_id, [str(s.seat_id) for s in seats])
    if on_paid is not None:
        try:
            await on_paid(order)
        except Exception:  # the sale stands whatever happens to the email
            log.exception("after-payment hook failed for order %s", order.id)
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
    order_of_seats = list(labels)
    exp = tokens.expiry_for(out.show.ends_at)
    tickets = sorted(
        await db.scalars(select(Ticket).where(Ticket.order_id == order.id)),
        key=lambda t: order_of_seats.index(str(t.seat_id)),
    )
    return TicketBundle(
        order=out,
        tickets=[
            TicketOut(
                id=t.id,
                seat_id=str(t.seat_id),
                label=labels[str(t.seat_id)].label,
                tier_label=labels[str(t.seat_id)].tier_label,
                qr_token=tokens.sign(settings, t.id, t.show_id, exp),
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
    scanned = (
        {
            oid: n
            for oid, n in (
                await db.execute(
                    select(Ticket.order_id, func.count())
                    .where(
                        Ticket.order_id.in_([o.id for o in orders]),
                        Ticket.checked_in_at.is_not(None),
                    )
                    .group_by(Ticket.order_id)
                )
            ).tuples()
        }
        if orders
        else {}
    )
    groups: list[TicketGroup] = []
    cache: dict[uuid.UUID, tuple[OrderShow, Screen]] = {}
    for order in orders:
        if order.show_id not in cache:
            cache[order.show_id] = await show_out(db, order.show_id)
        show, screen = cache[order.show_id]
        seats = await seats_out(db, order, screen)
        groups.append(
            TicketGroup(
                order_id=order.id,
                show=show,
                seats=[s.label for s in seats],
                tier_labels=list(dict.fromkeys(s.tier_label for s in seats)),
                total_paise=order.total_paise,
                paid_at=order.paid_at,
                checked_in=scanned.get(order.id, 0),
            )
        )
    upcoming = sorted((g for g in groups if g.show.ends_at > now), key=lambda g: g.show.starts_at)
    past = sorted(
        (g for g in groups if g.show.ends_at <= now), key=lambda g: g.show.starts_at, reverse=True
    )
    return MyTickets(upcoming=upcoming, past=past)
