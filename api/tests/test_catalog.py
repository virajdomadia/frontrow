"""B1, B3–B4: the catalogue that never empties, home + search, the movie page, showtimes by
cinema with availability colours, and the seat-map routes (show detail, layout, closed shows)."""

import uuid
from datetime import UTC, datetime, time, timedelta

import pytest
from fastapi import FastAPI
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.models import Business, Film, Show
from app.models.enums import ShowStatus
from app.routers.catalog import cache_until
from app.seed import seed
from app.seed.content import FILMS
from app.services import catalog
from app.services.schedules import IST, ist_today
from tests.helpers import open_show, tab

pytestmark = [pytest.mark.db]


def released(now: datetime) -> set[str]:
    """Titles out by `now` (IST) — the catalogue's real release dates decide "now showing"."""
    return {f.title for f in FILMS if f.release <= ist_today(now)}


async def test_home_and_search(db_engine: AsyncEngine, db: AsyncSession) -> None:
    now = datetime.now(UTC)
    await seed(db_engine, now=now)
    home = await catalog.home(db, now=now)
    assert {c.title for c in home.now_showing} == released(now)
    assert all(c.show_count > 0 and c.from_price_paise for c in home.now_showing)
    coming = [c.title for c in home.coming_soon]
    assert set(coming) == {f.title for f in FILMS} - released(now)
    release = {f.title: f.release for f in FILMS}
    assert coming == sorted(coming, key=lambda t: release[t])

    found = await catalog.search(db, "dune", now=now)
    assert [f.title for f in found.films] == ["Dune: Part Three"]
    comedy = {f.title for f in (await catalog.search(db, "comedy", now=now)).films}
    assert comedy == {"How to Rob a Bank", "Golmaal 5"}
    assert (await catalog.search(db, "zzz", now=now)).films == []


async def test_real_catalogue_facts(db_engine: AsyncEngine, db: AsyncSession) -> None:
    """Certificates as the CBFC issued them (age-banded U/A) or none yet; a runtime that isn't
    announced stays unknown rather than invented."""
    now = datetime.now(UTC)
    await seed(db_engine, now=now)
    ypml = await catalog.film_detail(db, "yeh-prem-mol-liya", now=now)
    assert ypml.cert == "UA 13+" and ypml.runtime_min == 173
    king = await catalog.film_detail(db, "king", now=now)
    assert king.cert is None and king.runtime_min is None and king.trailer_url is None
    assert king.poster_url == "/img/posters/king.png"
    assert [c.name for c in king.cast_crew[:2]] == ["Siddharth Anand", "Shah Rukh Khan"]


async def test_coming_soon_opens_on_release_day(db_engine: AsyncEngine, db: AsyncSession) -> None:
    """A coming-soon film has no shows before its release date; on the day it turns now showing
    with no reseed (the day's first read flips it) and its shows are on sale."""
    now = datetime.now(UTC)
    await seed(db_engine, now=now)
    upcoming = [f for f in FILMS if f.release > ist_today(now)]
    if not upcoming:
        pytest.skip("every film in the catalogue is out already")
    spec = min(upcoming, key=lambda f: f.release)
    film = await db.scalar(select(Film).where(Film.slug == spec.slug))
    assert film is not None
    first = await db.scalar(select(func.min(Show.starts_at)).where(Show.film_id == film.id))
    assert first is None or first.astimezone(IST).date() >= spec.release
    on_the_day = datetime.combine(spec.release, time(9, 0), IST).astimezone(UTC)
    home = await catalog.home(db, now=on_the_day)
    assert spec.title in {c.title for c in home.now_showing}
    assert spec.title not in {c.title for c in home.coming_soon}


async def test_catalogue_never_empties(db_engine: AsyncEngine, db: AsyncSession) -> None:
    """B1 done-when: films on sale today, and still a month later with no reseed and no cron
    — the first read after the horizon moves materialises the missing days."""
    now = datetime.now(UTC)
    await seed(db_engine, now=now)
    later = now + timedelta(days=31)
    before = await db.scalar(select(func.count()).select_from(Show).where(Show.starts_at > later))
    assert before == 0
    home = await catalog.home(db, now=later)
    assert {c.title for c in home.now_showing} == released(later)
    shows = await catalog.film_shows(
        db, "ramayana-part-1", day=None, language=None, format=None, now=later
    )
    assert shows.cinemas and all(s.starts_at > later for c in shows.cinemas for s in c.shows)
    # Idempotent: reading again creates nothing new.
    count = await db.scalar(select(func.count()).select_from(Show))
    await catalog.home(db, now=later)
    assert await db.scalar(select(func.count()).select_from(Show)) == count


async def test_movie_page_and_showtimes(db_engine: AsyncEngine, db: AsyncSession) -> None:
    now = datetime.now(UTC)
    await seed(db_engine, now=now)
    film = await catalog.film_detail(db, "ramayana-part-1", now=now)
    assert film.cert == "U" and film.runtime_min == 195 and film.cast_crew[0].role == "Director"
    versions = {(v.language, v.format) for v in film.versions}
    assert {("Hindi", "2D"), ("Kannada", "2D"), ("Tamil", "2D"), ("Telugu", "2D")} <= versions

    tamil = await catalog.film_shows(
        db, "ramayana-part-1", day=None, language="Tamil", format="2D", now=now
    )
    assert [c.name for c in tamil.cinemas] == ["Nandi Screens · Koramangala"]
    assert all(s.language == "Tamil" and s.starts_at > now for s in tamil.cinemas[0].shows)
    assert len(tamil.dates) == 7 and tamil.dates[0].date == now.astimezone(IST).date()
    day = tamil.dates[3].date
    later = await catalog.film_shows(
        db, "ramayana-part-1", day=day, language="Hindi", format="2D", now=now
    )
    assert later.date == day
    assert all(s.starts_at.astimezone(IST).date() == day for c in later.cinemas for s in c.shows)
    whitefield = next(c for c in later.cinemas if c.name == "Orbit Cinemas · Whitefield")
    assert [t.label for t in whitefield.shows[0].tiers] == ["Classic", "Prime", "Recliner"]

    # The pending business (Lakeview) never shows up; once approved, it does.
    everywhere = await catalog.film_shows(
        db, "yeh-prem-mol-liya", day=None, language="Hindi", format="2D", now=now
    )
    names = {c.name for d in [everywhere] for c in d.cinemas}
    assert not any("Lakeview" in n for n in names)
    await db.execute(
        update(Business).where(Business.slug == "lakeview-pictures").values(status="verified")
    )
    await db.commit()
    all_days = [
        await catalog.film_shows(
            db, "yeh-prem-mol-liya", day=d.date, language="Hindi", format="2D", now=now
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
    data = await catalog.film_shows(
        db, "ramayana-part-1", day=None, language=None, format=None, now=now
    )
    assert {s.fill for c in data.cinemas for s in c.shows} <= {"available", "filling", "sold_out"}


async def test_routes_over_http(db_engine: AsyncEngine, db: AsyncSession, db_app: FastAPI) -> None:
    await seed(db_engine, now=datetime.now(UTC))
    found = await open_show(db, "stalls_balcony", tiers=3)
    async with tab(db_app) as c:
        home = await c.get("/home")
        assert home.status_code == 200 and "s-maxage=60" in home.headers["cache-control"]
        assert (await c.get("/films", params={"q": "ramayana"})).json()["films"][0][
            "slug"
        ] == "ramayana-part-1"
        assert (await c.get("/films/no-such-film")).status_code == 404
        listing = await c.get(
            "/films/ramayana-part-1/shows", params={"language": "Kannada", "format": "2D"}
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
