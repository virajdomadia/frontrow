"""B1: the seed — idempotent and non-destructive, believable halls, demo bookings."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.models import Business, Film, FilmRequest, Order, Screen, Show, Ticket, User
from app.models.enums import BusinessStatus, OrderStatus
from app.seed import check_no_overlap, seed
from app.seed.content import DEMO_CUSTOMER
from app.services.orders import my_tickets

pytestmark = pytest.mark.db


async def _counts(db: AsyncSession) -> tuple[int, ...]:
    return tuple(
        [
            await db.scalar(select(func.count()).select_from(t)) or 0
            for t in (User, Business, Film, Screen, Show, Ticket, FilmRequest)
        ]
    )


def test_seed_slots_never_overlap() -> None:
    check_no_overlap()


async def test_seed_twice_is_idempotent(db_engine: AsyncEngine, db: AsyncSession) -> None:
    now = datetime.now(UTC)
    first = await seed(db_engine, now=now)
    assert first["films"] == 8 and first["businesses"] == 4 and first["new_shows"] > 50
    before = await _counts(db)
    again = await seed(db_engine, now=now)
    assert again["new_shows"] == 0
    assert await _counts(db) == before
    pending = await db.scalar(
        select(func.count()).select_from(Business).where(Business.status == BusinessStatus.PENDING)
    )
    assert pending == 1


async def test_halls_look_lived_in(db_engine: AsyncEngine, db: AsyncSession) -> None:
    now = datetime.now(UTC)
    await seed(db_engine, now=now)
    rows = (
        (
            await db.execute(
                select(Show.id, Screen.seat_count, func.count(Ticket.id))
                .join(Screen, Screen.id == Show.screen_id)
                .outerjoin(Ticket, Ticket.show_id == Show.id)
                .where(Show.starts_at > now)
                .group_by(Show.id, Screen.seat_count)
            )
        )
        .tuples()
        .all()
    )
    assert rows
    fills = [sold / seats for _, seats, sold in rows]
    assert all(f < 1 for f in fills)  # never a sold-out show from the seed: a seat is always free
    assert max(fills) > 0.3 and sum(1 for f in fills if f > 0) > len(fills) / 2


async def test_demo_customer_has_bookings(db_engine: AsyncEngine, db: AsyncSession) -> None:
    now = datetime.now(UTC)
    await seed(db_engine, now=now)
    customer = await db.scalar(select(User).where(User.email == DEMO_CUSTOMER))
    assert customer is not None
    mine = await my_tickets(db, customer, now=now)
    assert len(mine.upcoming) == 1 and len(mine.past) == 1
    assert len(mine.upcoming[0].seats) == 2
    assert mine.past[0].checked_in == 2  # scanned in at the door

    # A week later the upcoming one has been played; signing in again books a fresh one.
    from app.services.demo import ensure_bookings

    later = now + timedelta(days=8)
    await ensure_bookings(db, None, customer, now=later)
    again = await my_tickets(db, customer, now=later)
    assert len(again.upcoming) == 1 and len(again.past) == 2
    paid = await db.scalar(
        select(func.count())
        .select_from(Order)
        .where(Order.user_id == customer.id, Order.status == OrderStatus.PAID)
    )
    assert paid == 3


async def test_reset(db_engine: AsyncEngine, db: AsyncSession) -> None:
    now = datetime.now(UTC)
    await seed(db_engine, now=now)
    report = await seed(db_engine, now=now, reset=True)
    assert report["new_shows"] > 50
