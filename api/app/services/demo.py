"""Keeps the one-click demo customer believable (R1): whenever they sign in, they have an
upcoming booking — a pair of good seats at a show a few days out — next to the past one the seed
gave them. Shows roll forward on their own (`schedules.materialise`), so this only books when
the last upcoming booking has been played. Touches demo and seeded data only."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Business, Cinema, Film, Order, Screen, Show, ShowPrice, User
from app.models.enums import BusinessStatus, FilmStatus, OrderStatus, ShowStatus
from app.services import holds
from app.services.schedules import IST, _Batch, materialise
from app.services.shows import sold_seats

log = logging.getLogger(__name__)

DEMO_BUSINESS = "orbit-cinemas"


def centre_pair(screen: Screen, tier: str, taken: set[str], size: int = 2) -> list[str] | None:
    """`size` adjacent free seats as close to the middle of `tier` as possible."""
    rows = [r for s in screen.layout["sections"] if s["tier"] == tier for r in s["rows"]]
    middle = len(rows) / 2
    for _, row in sorted(enumerate(rows), key=lambda ir: abs(ir[0] - middle)):
        seats = row["seats"]
        mid = len(seats) // 2
        starts = sorted(range(len(seats) - size + 1), key=lambda i: abs(i + size / 2 - mid))
        for i in starts:
            run = [s["id"] for s in seats[i : i + size]]
            if not taken & set(run):
                return run
    return None


async def ensure_bookings(
    db: AsyncSession, redis: Redis | None, customer: User, *, now: datetime
) -> None:
    upcoming = await db.scalar(
        select(Order.id)
        .join(Show, Show.id == Order.show_id)
        .where(
            Order.user_id == customer.id,
            Order.status == OrderStatus.PAID,
            Show.starts_at > now + timedelta(hours=3),
        )
        .limit(1)
    )
    if upcoming is not None:
        return
    await materialise(db, now=now)
    rows = (
        (
            await db.execute(
                select(Show, Screen)
                .join(Screen, Screen.id == Show.screen_id)
                .join(Cinema, Cinema.id == Screen.cinema_id)
                .join(Business, Business.id == Cinema.business_id)
                .join(Film, Film.id == Show.film_id)
                .where(
                    Business.slug == DEMO_BUSINESS,
                    Business.status == BusinessStatus.VERIFIED,
                    Film.status == FilmStatus.NOW_SHOWING,
                    Show.status == ShowStatus.SCHEDULED,
                    Show.starts_at > now + timedelta(days=2),
                    Show.starts_at < now + timedelta(days=6),
                )
                .order_by(Show.starts_at)
            )
        )
        .tuples()
        .all()
    )
    for show, screen in rows:
        if (
            show.starts_at.astimezone(IST).hour < 12
        ):  # an evening show reads better than a 9:30 a.m. one
            continue
        prices = {
            p.tier_key: p.price_paise
            for p in await db.scalars(select(ShowPrice).where(ShowPrice.show_id == show.id))
        }
        tier = next((t["key"] for t in reversed(screen.tiers) if t["key"] in prices), None)
        if tier is None:
            continue
        live = await holds.snapshot(redis, show.id, None, now=now)
        taken = set(await sold_seats(db, show.id)) | {h.seat_id for h in live.others}
        pair = centre_pair(screen, tier, taken)
        if pair is None:
            continue
        batch = _Batch(show.id)
        batch.order(pair, tier, prices[tier], customer.id, now - timedelta(minutes=5), "UPI")
        await batch.insert(db)
        await db.commit()
        await holds.clear_sold(redis, show.id, pair)
        return
    log.warning("no show to give the demo customer an upcoming booking")
