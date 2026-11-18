"""F1: the seat-map routes — detail, immutable layout, and sold seats straight from tickets —
and the closed guard: a started or cancelled showtime answers 410, like the web's book page."""

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.models import Showtime, Ticket, Venue
from app.models.enums import ShowtimeStatus
from app.routers.events import cache_until
from app.seed import seed

pytestmark = pytest.mark.db


def real_now() -> datetime:
    # The routes read the real clock (the closed guard), so seed relative to it: every seeded
    # showtime is then in the future.
    return datetime.now(UTC)


async def test_seat_map_routes(
    db_engine: AsyncEngine, db: AsyncSession, db_client: AsyncClient
) -> None:
    await seed(db_engine, now=real_now())
    showtime, venue = (
        await db.execute(
            select(Showtime, Venue)
            .join(Venue, Venue.id == Showtime.venue_id)
            .where(Venue.template == "arena", Showtime.starts_at > real_now())
            .order_by(Showtime.starts_at)
            .limit(1)
        )
    ).one()
    sold = {
        str(s)
        for s in await db.scalars(select(Ticket.seat_id).where(Ticket.showtime_id == showtime.id))
    }

    detail = await db_client.get(f"/showtimes/{showtime.id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["venue"]["template"] == "arena"
    assert [t["tier_key"] for t in body["tiers"]] == ["floor", "gold", "silver", "bronze"]
    assert body["seats_left"] == venue.seat_count - len(sold)

    layout = await db_client.get(body["layout_url"])
    assert layout.status_code == 200 and "immutable" in layout.headers["cache-control"]
    ids = {s["id"] for sec in layout.json()["sections"] for r in sec["rows"] for s in r["seats"]}
    assert len(ids) == venue.seat_count

    seats = await db_client.get(f"/showtimes/{showtime.id}/seats")
    assert seats.status_code == 200 and seats.headers["cache-control"] == "no-store"
    state = seats.json()
    assert set(state["sold"]) == sold and sold <= ids
    assert state["held"] == [] and state["mine"] == []  # Redis holds arrive in F2

    for path in ("/showtimes/nope", "/showtimes/00000000-0000-0000-0000-000000000000/seats"):
        missing = await db_client.get(path)
        assert missing.status_code == 404 and missing.json()["error"]["code"] == "not_found"


@pytest.mark.parametrize("why", ["started", "cancelled"])
async def test_closed_showtimes_are_gone(
    db_engine: AsyncEngine, db: AsyncSession, db_client: AsyncClient, why: str
) -> None:
    await seed(db_engine, now=real_now())
    showtime = await db.scalar(
        select(Showtime).where(Showtime.starts_at > real_now()).order_by(Showtime.starts_at)
    )
    assert showtime is not None
    change = (
        {"starts_at": real_now() - timedelta(minutes=5)}
        if why == "started"
        else {"status": ShowtimeStatus.CANCELLED}
    )
    await db.execute(update(Showtime).where(Showtime.id == showtime.id).values(**change))
    await db.commit()

    for path in (f"/showtimes/{showtime.id}", f"/showtimes/{showtime.id}/seats"):
        res = await db_client.get(path)
        assert res.status_code == 410, path
        error = res.json()["error"]
        assert error["code"] == "showtime_closed" and error["details"]["reason"] == why
        assert error["details"]["event_slug"]
        assert "s-maxage" not in res.headers.get("cache-control", "")


def test_cache_never_outlives_the_deadline() -> None:
    now = datetime(2026, 11, 19, 18, 29, 30, tzinfo=UTC)  # 23:59:30 IST
    assert cache_until(now + timedelta(hours=2), now) == (
        "public, s-maxage=60, stale-while-revalidate=300"
    )
    # 30 s to midnight: fresh for 30, and no stale window past it.
    assert cache_until(now + timedelta(seconds=30), now) == (
        "public, s-maxage=30, stale-while-revalidate=0"
    )
    assert cache_until(now - timedelta(seconds=1), now) == "no-store"
