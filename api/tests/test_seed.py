"""R9: the seed runs twice without duplicates; every showtime has a sold and a free seat."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.models import Event, Seat, Showtime, Ticket, User, Venue
from app.seed import seed
from app.seed.content import EVENTS, SHOWTIMES, VENUES

pytestmark = pytest.mark.db

NOW = datetime(2026, 9, 18, 12, 0, tzinfo=UTC)


async def _counts(db: AsyncSession) -> dict[str, int]:
    out = {}
    for name, model in (
        ("users", User),
        ("venues", Venue),
        ("seats", Seat),
        ("events", Event),
        ("showtimes", Showtime),
        ("tickets", Ticket),
    ):
        out[name] = (await db.scalar(select(func.count()).select_from(model))) or 0
    return out


async def test_seed_twice_is_idempotent(db_engine: AsyncEngine, db: AsyncSession) -> None:
    first = await seed(db_engine, now=NOW)
    counts = await _counts(db)
    assert counts["venues"] == len(VENUES) and counts["events"] == len(EVENTS)
    assert counts["showtimes"] == len(SHOWTIMES)
    assert counts["seats"] == (await db.scalar(select(func.sum(Venue.seat_count))))
    assert first["tickets"] == counts["tickets"] > 0

    seat_ids_before = set(await db.scalars(select(Seat.id)))
    second = await seed(db_engine, now=NOW)
    db.expire_all()
    assert await _counts(db) == counts
    assert dict(second) == dict(first)
    # Venues (and their seat ids) survive a re-run — holds and tickets key on them.
    assert set(await db.scalars(select(Seat.id))) == seat_ids_before


async def test_every_showtime_has_a_sold_and_a_free_seat(
    db_engine: AsyncEngine, db: AsyncSession
) -> None:
    await seed(db_engine, now=NOW)
    rows = (await db.execute(text("select seat_count, sold from showtime_fill"))).all()
    assert len(rows) == len(SHOWTIMES)
    for seat_count, sold in rows:
        assert 0 < sold < seat_count
    # The "filling fast" opening night is ≥ 90 % sold; nothing is sold out.
    assert max(sold / seat_count for seat_count, sold in rows) >= 0.9
    # Everything is in the future relative to the seed's clock.
    earliest = await db.scalar(select(func.min(Showtime.starts_at)))
    assert earliest is not None and earliest > NOW
