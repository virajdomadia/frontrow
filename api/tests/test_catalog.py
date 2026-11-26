"""B1, B3–B4: the catalogue that never empties, home + search, the movie page, showtimes by
cinema with availability colours, and the seat-map routes (show detail, layout, closed shows)."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.models import Business, Film, Show
from app.models.enums import ShowStatus
from app.routers.catalog import cache_until
from app.seed import seed
from app.services import catalog
from app.services.schedules import IST
from tests.helpers import open_show, tab

pytestmark = [pytest.mark.db]


async def test_home_and_search(db_engine: AsyncEngine, db: AsyncSession) -> None:
    now = datetime.now(UTC)
    await seed(db_engine, now=now)
    home = await catalog.home(db, now=now)
    titles = [c.title for c in home.now_showing]
    assert len(titles) == 7 and "The Rhythm Collective" not in titles
    assert all(c.show_count > 0 and c.from_price_paise for c in home.now_showing)
    assert [c.title for c in home.coming_soon] == ["The Rhythm Collective"]

    found = await catalog.search(db, "dune", now=now)
    assert [f.title for f in found.films] == ["The Last Dune"]
    assert [f.title for f in (await catalog.search(db, "comedy", now=now)).films] == [
        "Static Bloom",
        "The Rhythm Collective",
    ]
    assert (await catalog.search(db, "zzz", now=now)).films == []


async def test_catalogue_never_empties(db_engine: AsyncEngine, db: AsyncSession) -> None:
    """B1 done-when: films on sale today, and still a month later with no reseed and no cron
    — the first read after the horizon moves materialises the missing days."""
    now = datetime.now(UTC)
    await seed(db_engine, now=now)
    later = now + timedelta(days=31)
    before = await db.scalar(select(func.count()).select_from(Show).where(Show.starts_at > later))
    assert before == 0
    home = await catalog.home(db, now=later)
    assert len(home.now_showing) == 7
    shows = await catalog.film_shows(
        db, "neon-alley", day=None, language=None, format=None, now=later
    )
    assert shows.cinemas and all(s.starts_at > later for c in shows.cinemas for s in c.shows)
    # Idempotent: reading again creates nothing new.
    count = await db.scalar(select(func.count()).select_from(Show))
    await catalog.home(db, now=later)
    assert await db.scalar(select(func.count()).select_from(Show)) == count


async def test_movie_page_and_showtimes(db_engine: AsyncEngine, db: AsyncSession) -> None:
    now = datetime.now(UTC)
    await seed(db_engine, now=now)
    film = await catalog.film_detail(db, "the-last-dune", now=now)
    assert film.cert == "UA" and film.runtime_min == 152 and film.cast_crew[0].role == "Director"
    versions = {(v.language, v.format) for v in film.versions}
    assert {("English", "IMAX"), ("English", "3D"), ("Hindi", "2D")} <= versions

    imax = await catalog.film_shows(
        db, "the-last-dune", day=None, language="English", format="IMAX", now=now
    )
    assert [c.name for c in imax.cinemas] == ["Orbit Cinemas · Whitefield"]
    assert all(s.format == "IMAX" and s.starts_at > now for s in imax.cinemas[0].shows)
    assert len(imax.dates) == 7 and imax.dates[0].date == now.astimezone(IST).date()
    day = imax.dates[3].date
    later = await catalog.film_shows(
        db, "the-last-dune", day=day, language="English", format="IMAX", now=now
    )
    assert later.date == day
    assert all(s.starts_at.astimezone(IST).date() == day for c in later.cinemas for s in c.shows)
    tiers = later.cinemas[0].shows[0].tiers
    assert [t.label for t in tiers] == ["Classic", "Prime", "Recliner"]

    # The pending business (Lakeview) never shows up; once approved, it does.
    everywhere = await catalog.film_shows(
        db, "glass-city", day=None, language="Kannada", format="2D", now=now
    )
    names = {c.name for d in [everywhere] for c in d.cinemas}
    assert not any("Lakeview" in n for n in names)
    await db.execute(
        update(Business).where(Business.slug == "lakeview-pictures").values(status="verified")
    )
    await db.commit()
    all_days = [
        await catalog.film_shows(
            db, "glass-city", day=d.date, language="Kannada", format="2D", now=now
        )
        for d in everywhere.dates
    ]
    assert any("Lakeview" in c.name for d in all_days for c in d.cinemas)


async def test_availability_colours(db_engine: AsyncEngine, db: AsyncSession) -> None:
    assert catalog.fill_of(100, 100) == "sold_out"
    assert catalog.fill_of(100, 50, 20) == "filling"
    assert catalog.fill_of(100, 50, 19) == "available"
    now = datetime.now(UTC)
    await seed(db_engine, now=now)
    data = await catalog.film_shows(db, "neon-alley", day=None, language=None, format=None, now=now)
    assert {s.fill for c in data.cinemas for s in c.shows} <= {"available", "filling", "sold_out"}


async def test_routes_over_http(db_engine: AsyncEngine, db: AsyncSession, db_app: FastAPI) -> None:
    await seed(db_engine, now=datetime.now(UTC))
    found = await open_show(db, "stalls_balcony", tiers=3)
    async with tab(db_app) as c:
        home = await c.get("/home")
        assert home.status_code == 200 and "s-maxage=60" in home.headers["cache-control"]
        assert (await c.get("/films", params={"q": "neon"})).json()["films"][0][
            "slug"
        ] == "neon-alley"
        assert (await c.get("/films/no-such-film")).status_code == 404
        listing = await c.get(
            "/films/hollowmere/shows", params={"language": "Kannada", "format": "2D"}
        )
        assert listing.status_code == 200 and listing.json()["language"] == "Kannada"

        detail = (await c.get(f"/shows/{found.show.id}")).json()
        assert detail["screen"]["template"] == "stalls_balcony"
        assert detail["fee_paise"] == 3000 and detail["layout_url"].startswith("/screens/")
        assert [t["tier_key"] for t in detail["tiers"]] == ["front", "rear", "balcony"]
        layout = await c.get(detail["layout_url"])
        assert layout.status_code == 200 and "immutable" in layout.headers["cache-control"]
        assert layout.json()["stage"]["label"] == "SCREEN"
        seats = await c.get(f"/shows/{found.show.id}/seats")
        assert seats.headers["cache-control"] == "no-store" and seats.json()["sold"] is not None
        assert (await c.get(f"/shows/{uuid.uuid4()}")).status_code == 404
        assert (await c.get("/shows/not-a-uuid")).status_code == 404


@pytest.mark.parametrize("how", ["cancelled", "started"])
async def test_closed_shows_are_gone(
    how: str, db_engine: AsyncEngine, db: AsyncSession, db_app: FastAPI
) -> None:
    await seed(db_engine, now=datetime.now(UTC))
    found = await open_show(db)
    values = (
        {"status": ShowStatus.CANCELLED}
        if how == "cancelled"
        else {"starts_at": datetime.now(UTC) - timedelta(minutes=5)}
    )
    await db.execute(update(Show).where(Show.id == found.show.id).values(**values))
    await db.commit()
    film = await db.get(Film, found.show.film_id)
    assert film is not None
    async with tab(db_app) as c:
        res = await c.get(f"/shows/{found.show.id}")
        assert res.status_code == 410
        err = res.json()["error"]
        assert err["code"] == "show_closed" and err["details"]["reason"] == how
        assert err["details"]["film_slug"] == film.slug
        hold = await c.post(f"/shows/{found.show.id}/holds", json={"seat_ids": found.all_free[:1]})
        assert hold.status_code in (410, 503)


def test_cache_never_outlives_the_deadline() -> None:
    now = datetime(2026, 11, 26, 12, 0, tzinfo=UTC)
    assert cache_until(now + timedelta(hours=2), now).startswith("public, s-maxage=60")
    assert cache_until(now + timedelta(seconds=30), now) == (
        "public, s-maxage=30, stale-while-revalidate=0"
    )
    assert cache_until(now - timedelta(seconds=1), now) == "no-store"
