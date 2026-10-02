"""F1: the seat-map routes — detail, immutable layout, and sold seats straight from tickets."""

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.models import Showtime, Ticket, Venue
from app.seed import seed

pytestmark = pytest.mark.db

NOW = datetime(2026, 9, 18, 12, 0, tzinfo=UTC)


async def test_seat_map_routes(
    db_engine: AsyncEngine, db: AsyncSession, db_client: AsyncClient
) -> None:
    await seed(db_engine, now=NOW)
    showtime, venue = (
        await db.execute(
            select(Showtime, Venue)
            .join(Venue, Venue.id == Showtime.venue_id)
            .where(Venue.template == "arena")
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
