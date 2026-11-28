"""Running the day at a cinema (v2): the Today board and blocked seats (L3).

Every write here goes through the owner's own show (another business's id → 404) and the
per-show lock (`shows.show_lock`) that `orders.confirm` also takes, so a block and a sale of the
same seat can't both win: whichever commits first, the other sees it.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from redis.asyncio import Redis
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import ApiError
from app.models import (
    BlockedSeat,
    Business,
    Cinema,
    EmailOutbox,
    Film,
    Order,
    OrderSeat,
    Screen,
    Seat,
    Show,
    ShowPrice,
    Ticket,
    User,
)
from app.models.enums import OrderChannel, OrderStatus, ShowStatus
from app.schemas.owner import CancelResult, OwnerToday, RecentOrder
from app.services import holds, outbox
from app.services import orders as order_svc
from app.services import owner as owner_svc
from app.services.auth import initials
from app.services.mail import Mailer
from app.services.orders import PAY_WINDOW
from app.services.payments import Gateway
from app.services.schedules import IST, ist_today
from app.services.shows import check_seats, parse_id, show_lock, taken_seats

RECENT = 8


async def own_show_row(
    db: AsyncSession, business: Business, show_id: str | uuid.UUID
) -> tuple[Show, Screen]:
    """The business's own show with its screen, else 404 (never another business's)."""
    row = (
        await db.execute(
            select(Show, Screen)
            .join(Screen, Screen.id == Show.screen_id)
            .join(Cinema, Cinema.id == Screen.cinema_id)
            .where(Show.id == parse_id(show_id), Cinema.business_id == business.id)
        )
    ).one_or_none()
    if row is None:
        raise ApiError("not_found", "No such show")
    return row._tuple()


def _open(show: Show, now: datetime) -> None:
    if show.status == ShowStatus.CANCELLED:
        raise ApiError("show_closed", "This show was cancelled", status=410)
    if show.starts_at <= now:
        raise ApiError("show_closed", "This show has already started", status=410)


async def today(db: AsyncSession, business: Business, now: datetime, *, demo: bool) -> OwnerToday:
    """Every show today with fill, plus today's tickets, revenue and latest sales."""
    day = await owner_svc.shows_on(db, business, None, now)
    lo = datetime.combine(ist_today(now), datetime.min.time(), tzinfo=IST)
    rows = (
        await db.execute(
            select(Order, User, Show, Film, Screen, func.count(OrderSeat.seat_id))
            .join(User, User.id == Order.user_id)
            .join(Show, Show.id == Order.show_id)
            .join(Film, Film.id == Show.film_id)
            .join(Screen, Screen.id == Show.screen_id)
            .join(Cinema, Cinema.id == Screen.cinema_id)
            .join(OrderSeat, OrderSeat.order_id == Order.id)
            .where(
                Cinema.business_id == business.id,
                Order.status == OrderStatus.PAID,
                Order.paid_at >= lo,
                Order.paid_at < lo + timedelta(days=1),
            )
            .group_by(Order.id, User.id, Show.id, Film.id, Screen.id)
            .order_by(Order.paid_at.desc())
            .limit(RECENT)
        )
    ).tuples()
    recent = [
        RecentOrder(
            order_id=o.id,
            show_id=s.id,
            film_title=f.title,
            starts_at=s.starts_at,
            screen_name=sc.name,
            name=initials(u.name) if demo else u.name,  # the demo owner's customers are real
            seats=n,
            amount_paise=o.subtotal_paise,
            channel=o.channel.value,  # type: ignore[arg-type]
            paid_at=o.paid_at or o.created_at,
        )
        for o, u, s, f, sc, n in rows
    ]
    return OwnerToday(
        date=day.date,
        shows=day.shows,
        tickets=sum(s.sold for s in day.shows),
        revenue_paise=sum(s.revenue_paise for s in day.shows),
        recent=recent,
    )


async def block(
    db: AsyncSession,
    redis: Redis | None,
    business: Business,
    show_id: str,
    seat_ids: list[str],
    reason: str,
    *,
    holder: str | None,
    now: datetime,
) -> list[str]:
    """Take seats off sale, all or none: a sold seat, or one a customer is holding (they may be
    paying for it), is a 409 naming it."""
    show, _ = await own_show_row(db, business, show_id)
    _open(show, now)
    ids = await check_seats(db, show, seat_ids)
    await _not_busy(db, redis, show, ids, holder=holder, now=now)
    await show_lock(db, show.id)
    sold, _ = await taken_seats(db, show.id)
    gone = set(sold) & set(ids)
    if gone:
        raise ApiError(
            "seat_taken", "That seat is sold", status=409, details={"taken": sorted(gone)}
        )
    await db.execute(
        insert(BlockedSeat)
        .values([{"show_id": show.id, "seat_id": uuid.UUID(i), "reason": reason} for i in ids])
        .on_conflict_do_nothing()
    )
    await db.commit()
    await holds.announce(redis, show.id, "s")
    return ids


async def _not_busy(
    db: AsyncSession,
    redis: Redis | None,
    show: Show,
    ids: list[str],
    *,
    holder: str | None,
    now: datetime,
) -> None:
    """409 `seat_held` for a seat a customer is holding, or paying for: a block or a counter
    sale must not pull it from under them (they would only be refunded)."""
    live = await holds.snapshot(redis, show.id, holder, now=now)
    busy = {h.seat_id for h in live.others} & set(ids)
    # A hold lapses at 10 minutes but checkout stays open for 15: don't block a seat someone may
    # be paying for right now (they would only be refunded).
    paying = {
        str(s)
        for s in await db.scalars(
            select(OrderSeat.seat_id)
            .join(Order, Order.id == OrderSeat.order_id)
            .where(
                Order.show_id == show.id,
                Order.status == OrderStatus.PENDING,
                Order.channel == OrderChannel.ONLINE,
                Order.created_at > now - PAY_WINDOW,
            )
        )
    } & set(ids)
    if busy or paying:
        raise ApiError(
            "seat_held", "A customer is holding or paying for that seat right now", status=409,
            details={"taken": sorted(busy | paying)},
        )  # fmt: skip


async def unblock(
    db: AsyncSession,
    redis: Redis | None,
    business: Business,
    show_id: str,
    seat_ids: list[str],
    *,
    now: datetime,
) -> None:
    show, _ = await own_show_row(db, business, show_id)
    _open(show, now)
    ids = []
    for raw in dict.fromkeys(seat_ids):
        try:
            ids.append(uuid.UUID(raw))
        except ValueError:
            continue
    await db.execute(
        delete(BlockedSeat).where(BlockedSeat.show_id == show.id, BlockedSeat.seat_id.in_(ids))
    )
    await db.commit()
    await holds.announce(redis, show.id, "s")


async def counter_sale(
    db: AsyncSession,
    redis: Redis | None,
    business: Business,
    cashier: User,
    show_id: str,
    seat_ids: list[str],
    key: str,
    *,
    holder: str | None,
    now: datetime,
) -> Order:
    """A walk-in paid in cash (L4): a paid order with tickets, all or none, under the same per-show
    lock and `UNIQUE (show_id, seat_id)` as an online sale, so online and counter can never sell
    one seat twice. No convenience fee. `key` comes from the till: the same key again (a retry,
    a double tap) returns the first sale; the same key for other seats is a 409."""
    show, _ = await own_show_row(db, business, show_id)
    ids = await check_seats(db, show, seat_ids)

    async def same_sale() -> Order | None:
        found = await db.scalar(select(Order).where(Order.idempotency_key == key))
        if found is None:
            return None
        seats = {
            str(s)
            for s in await db.scalars(
                select(OrderSeat.seat_id).where(OrderSeat.order_id == found.id)
            )
        }
        if found.show_id != show.id or seats != set(ids):
            raise ApiError(
                "idempotency_conflict", "That sale key was already used for other seats",
                status=409,
            )  # fmt: skip
        return found

    if (found := await same_sale()) is not None:
        return found  # a replay works even once the show has started
    _open(show, now)
    await _not_busy(db, redis, show, ids, holder=holder, now=now)
    await show_lock(db, show.id)
    if (found := await same_sale()) is not None:  # a double tap that waited on the lock
        await db.commit()
        return found
    sold, blocked = await taken_seats(db, show.id)
    gone = (set(sold) | set(blocked)) & set(ids)
    if gone:
        raise ApiError(
            "seat_taken", "That seat isn't available", status=409,
            details={"taken": sorted(gone)},
        )  # fmt: skip
    prices = {
        p.tier_key: p.price_paise
        for p in await db.scalars(select(ShowPrice).where(ShowPrice.show_id == show.id))
    }
    seats = list(await db.scalars(select(Seat).where(Seat.id.in_([uuid.UUID(i) for i in ids]))))
    subtotal = sum(prices[s.tier_key] for s in seats)
    order = Order(
        user_id=cashier.id,
        sid=f"counter:{cashier.id}",
        show_id=show.id,
        channel=OrderChannel.COUNTER,
        status=OrderStatus.PAID,
        subtotal_paise=subtotal,
        fee_paise=0,
        total_paise=subtotal,
        payment_method="Cash at the counter",
        paid_at=now,
        idempotency_key=key,
    )
    try:
        db.add(order)
        await db.flush()
        db.add_all(
            OrderSeat(
                order_id=order.id, seat_id=s.id, tier_key=s.tier_key,
                price_paise=prices[s.tier_key],
            )
            for s in seats
        )  # fmt: skip
        # Tickets in ids order, so the till shows them as the cashier picked them.
        await db.execute(
            insert(Ticket),
            [
                {"id": uuid.uuid4(), "order_id": order.id, "show_id": show.id,
                 "seat_id": uuid.UUID(i), "user_id": cashier.id}
                for i in ids
            ],
        )  # fmt: skip
        await db.commit()
    except IntegrityError as e:
        # The show lock makes this unreachable for seats; it is the same key sent for another
        # show at the same moment (the key is unique everywhere, the lock is per show).
        await db.rollback()
        raise ApiError(
            "idempotency_conflict", "That sale key was already used for another sale", status=409
        ) from e
    await holds.clear_sold(redis, show.id, ids)
    return order


# --- L5: cancel a show ----------------------------------------------------------------------------


def rupees(paise: int) -> str:
    return f"₹{paise / 100:,.2f}".removesuffix(".00")


REFUND_BATCH = 25  # orders per call: a full hall is refunded over a few calls, each well in time


async def cancel_show(
    db: AsyncSession,
    redis: Redis | None,
    gateway: Gateway,
    mailer: Mailer | None,
    business: Business,
    show_id: str,
    reason: str,
    *,
    web_url: str,
    now: datetime,
) -> CancelResult:
    """Cancel a show, refund every buyer in full and email them. Safe to call again and again:
    the first call cancels (under the show lock, so no payment lands halfway) and later calls
    finish what's left: refunds the gateway didn't take, buyers beyond this call's batch, emails
    still queued. Each order is refunded exactly once (`orders.refund_order`)."""
    show, _ = await own_show_row(db, business, show_id)
    if show.status != ShowStatus.CANCELLED:
        if show.starts_at <= now:
            raise ApiError("show_closed", "This show has already started", status=410)
        await show_lock(db, show.id)
        show.status = ShowStatus.CANCELLED
        show.cancel_reason = reason
        await db.commit()
        await holds.announce(redis, show.id, "x")  # open seat maps close
    film = await db.get(Film, show.film_id)
    cinema = await db.scalar(
        select(Cinema)
        .join(Screen, Screen.cinema_id == Cinema.id)
        .where(Screen.id == show.screen_id)
    )
    assert film is not None and cinema is not None
    todo = list(
        await db.scalars(
            select(Order.id)
            .where(
                Order.show_id == show.id,
                (Order.status == OrderStatus.PAID)
                | (
                    (Order.status == OrderStatus.REFUNDED)
                    & Order.refund_id.is_(None)
                    & Order.razorpay_payment_id.is_not(None)
                ),
            )
            .order_by(Order.paid_at)
            .limit(REFUND_BATCH)
        )
    )
    when = show.starts_at.astimezone(IST).strftime("%a %d %b, %I:%M %p")
    for order_id in todo:
        order = await order_svc.refund_order(db, gateway, order_id, order_svc.SHOW_CANCELLED)
        if order.channel != OrderChannel.ONLINE or order.user_id is None:
            continue  # counter buyers get their cash back at the box office
        emailed = await db.scalar(
            select(EmailOutbox.id).where(
                EmailOutbox.order_id == order.id, EmailOutbox.kind == "show_cancelled"
            )
        )
        buyer = await db.get(User, order.user_id)
        if emailed is None and buyer is not None:
            outbox.queue(
                db, to=buyer.email, kind="show_cancelled", order_id=order.id,
                subject=f"Cancelled: {film.title}, {when}",
                text=(
                    f"{cinema.name} has cancelled {film.title} on {when}.\n\n"
                    f"Their reason: {reason}\n\n"
                    f"We've refunded {rupees(order.total_paise)} in full to the way you paid. "
                    "It reaches your account in 5 to 7 working days.\n\n"
                    f"Your order: {web_url.rstrip('/')}/checkout/{order.id}"
                ),
            )  # fmt: skip
            await db.commit()
    mails = list(
        await db.scalars(
            select(EmailOutbox.id)
            .join(Order, Order.id == EmailOutbox.order_id)
            .where(Order.show_id == show.id, EmailOutbox.kind == "show_cancelled")
        )
    )
    await outbox.deliver(db, mailer, mails, now=now)
    return await cancel_state(db, show.id)


async def cancel_state(db: AsyncSession, show_id: uuid.UUID) -> CancelResult:
    orders = list(await db.scalars(select(Order).where(Order.show_id == show_id)))
    statuses = (
        await db.execute(
            select(EmailOutbox.status, func.count())
            .join(Order, Order.id == EmailOutbox.order_id)
            .where(Order.show_id == show_id, EmailOutbox.kind == "show_cancelled")
            .group_by(EmailOutbox.status)
        )
    ).tuples()
    refunded = [o for o in orders if o.status == OrderStatus.REFUNDED]
    return CancelResult(
        refunded=len(refunded),
        refunded_paise=sum(o.total_paise for o in refunded),
        refund_pending=sum(1 for o in refunded if o.refund_id is None and o.razorpay_payment_id),
        remaining=sum(1 for o in orders if o.status == OrderStatus.PAID),
        emails={status: n for status, n in statuses},
    )
