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
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import ApiError
from app.models import BlockedSeat, Business, Cinema, Film, Order, OrderSeat, Screen, Show, User
from app.models.enums import OrderChannel, OrderStatus, ShowStatus
from app.schemas.owner import OwnerToday, RecentOrder
from app.services import holds
from app.services import owner as owner_svc
from app.services.auth import initials
from app.services.orders import PAY_WINDOW
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
