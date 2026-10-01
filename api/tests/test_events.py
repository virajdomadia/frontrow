"""R1/R2: URL filters render the right subset; past showtimes hidden; fill badges; envelope."""

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.errors import ApiError
from app.models import Showtime, Venue
from app.seed import seed
from app.seed.content import EVENTS, SHOWTIMES
from app.services import events as svc

pytestmark = pytest.mark.db

# 17:30 IST → the seed's day 0 is the next day, so "today" is empty and "tomorrow" is day 0.
NOW = datetime(2026, 9, 18, 12, 0, tzinfo=UTC)


async def test_list_and_filters(db_engine: AsyncEngine, db: AsyncSession) -> None:
    await seed(db_engine, now=NOW)
    listing = await svc.list_events(db, svc.ListParams(), now=NOW)
    assert listing.total == len(EVENTS) and listing.showtime_count == len(SHOWTIMES)
    starts = [c.next_showtime.starts_at for c in listing.events if c.next_showtime]
    assert starts == sorted(starts)  # soonest first
    assert listing.events[0].slug == "neon-alley" and listing.events[0].next_showtime
    assert listing.events[0].next_showtime.fill == "filling"  # 92 % sold opening night
    assert listing.events[0].from_price_paise == 22000
    assert [g.value for g in listing.genres] == sorted({e.genre for e in EVENTS})

    today = await svc.list_events(db, svc.ListParams(date="today"), now=NOW)
    assert today.total == 0  # nothing left today at 17:30 IST — the empty state
    tomorrow = await svc.list_events(db, svc.ListParams(date="tomorrow"), now=NOW)
    assert {c.slug for c in tomorrow.events} == {"neon-alley", "the-last-dune"}
    assert tomorrow.showtime_count == 2

    concerts = await svc.list_events(db, svc.ListParams(type="concert"), now=NOW)
    assert {c.slug for c in concerts.events} == {
        "static-bloom",
        "midnight-brass",
        "rhythm-collective-live",
    }
    jazz = await svc.list_events(db, svc.ListParams(genre="jazz"), now=NOW)
    assert [c.slug for c in jazz.events] == ["midnight-brass"]

    yard = await db.scalar(select(Venue).where(Venue.name == "The Yard Arena"))
    assert yard is not None
    at_yard = await svc.list_events(db, svc.ListParams(venue=yard.id), now=NOW)
    assert [c.slug for c in at_yard.events] == ["static-bloom"]
    assert at_yard.events[0].upcoming_count == 2

    by_price = await svc.list_events(db, svc.ListParams(sort="price"), now=NOW)
    prices = [c.from_price_paise or 0 for c in by_price.events]
    assert prices == sorted(prices)

    with pytest.raises(ApiError) as err:
        await svc.list_events(db, svc.ListParams(date="next-week"), now=NOW)
    assert err.value.code == "validation"


async def test_event_page_and_past_showtimes(db_engine: AsyncEngine, db: AsyncSession) -> None:
    await seed(db_engine, now=NOW)
    detail = await svc.get_event(db, "neon-alley", now=NOW)
    assert len(detail.showtimes) == 4
    first = detail.showtimes[0]
    assert first.fill == "filling" and first.seats_left == 234 - int(234 * 0.92)
    assert [t.tier_key for t in first.tiers] == ["classic", "prime", "recliner"]
    assert (first.price_min_paise, first.price_max_paise) == (22000, 55000)
    assert first.venue.name == "Orbit Cinemas · Screen 1"

    # Move the opening night into the past: it disappears from the page and the card.
    await db.execute(
        update(Showtime).where(Showtime.id == first.id).values(starts_at=NOW - timedelta(hours=3))
    )
    await db.commit()
    detail = await svc.get_event(db, "neon-alley", now=NOW)
    assert len(detail.showtimes) == 3
    assert detail.next_showtime and detail.next_showtime.id != first.id

    with pytest.raises(ApiError) as err:
        await svc.get_event(db, "atlantis", now=NOW)
    assert err.value.status == 404


async def test_home_strip(db_engine: AsyncEngine, db: AsyncSession) -> None:
    await seed(db_engine, now=NOW)
    home = await svc.home(db, now=NOW)
    assert len(home.now_showing) == 6 and home.now_showing[0].slug == "neon-alley"


async def test_routes_over_http(db_engine: AsyncEngine, db_client: AsyncClient) -> None:
    await seed(db_engine)  # relative to the real clock, like the routes
    res = await db_client.get("/events", params={"type": "movie", "sort": "title"})
    assert res.status_code == 200
    assert res.headers["cache-control"].startswith("public, s-maxage=60")
    titles = [e["title"] for e in res.json()["events"]]
    assert titles == sorted(titles) and len(titles) == 5

    res = await db_client.get("/events", params={"date": "someday"})
    assert res.status_code == 422 and res.json()["error"]["code"] == "validation"

    res = await db_client.get("/events/neon-alley")
    body = res.json()
    assert res.status_code == 200 and body["showtimes"][0]["venue"]["seat_count"] == 234

    res = await db_client.get("/events/atlantis")
    assert res.status_code == 404 and res.json()["error"]["code"] == "not_found"

    res = await db_client.get("/home")
    assert res.status_code == 200 and len(res.json()["now_showing"]) == 6

    # An event with no upcoming showtimes is not listed.
    slug = "glass-city"
    event_id = (await db_client.get(f"/events/{slug}")).json()["id"]
    async with db_engine.begin() as conn:
        await conn.execute(
            update(Showtime)
            .where(Showtime.event_id == event_id)
            .values(starts_at=datetime.now(UTC) - timedelta(days=1))
        )
    assert slug not in {e["slug"] for e in (await db_client.get("/events")).json()["events"]}
