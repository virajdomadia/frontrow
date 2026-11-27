"""B1: the seed — idempotent and non-destructive, believable halls, demo bookings."""

import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.models import Business, Film, FilmRequest, Order, Screen, Show, ShowPrice, Ticket, User
from app.models.enums import BusinessStatus, Cert, FilmStatus, OrderStatus, ShowStatus
from app.seed import check_no_overlap, seed
from app.seed.content import DEMO_CUSTOMER, FILMS, RETIRED_FILMS
from app.services import demo
from app.services.orders import my_tickets
from app.services.schedules import BOOKER_DOMAIN, _Batch, ends

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
    assert first["films"] == len(FILMS) and first["businesses"] == 4 and first["new_shows"] > 50
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


async def _old_film(db: AsyncSession, slug: str, screen: Screen, starts: datetime) -> Show:
    """A film of the first, fictional catalogue with one show, as production still has them."""
    film = Film(
        slug=slug, title=slug.replace("-", " ").title(), synopsis="An old demo film.",
        cast_crew=[{"name": "Someone", "role": "Director"}], runtime_min=120, cert=Cert.UA,
        genres=["Drama"], languages=["Hindi"], formats=["2D"],
        poster_url=f"/img/posters/{slug}.jpg", release_date=date(2026, 11, 1),
        status=FilmStatus.NOW_SHOWING,
    )  # fmt: skip
    db.add(film)
    await db.flush()
    show = Show(
        id=uuid.uuid4(), screen_id=screen.id, film_id=film.id, language="Hindi", format="2D",
        starts_at=starts, ends_at=ends(starts, 120), status=ShowStatus.SCHEDULED,
    )  # fmt: skip
    db.add(show)
    await db.flush()
    db.add_all(
        ShowPrice(show_id=show.id, tier_key=k, price_paise=16000)
        for k in [t["key"] for t in screen.tiers]
    )
    return show


async def test_reseed_retires_the_fictional_films(db_engine: AsyncEngine, db: AsyncSession) -> None:
    """Production was seeded with the fictional catalogue. Reseeding removes those films and
    the demo customer's bookings of them, rebooks the demo customer on real films, and keeps
    only what a real visitor holds a ticket for."""
    now = datetime.now(UTC)
    await seed(db_engine, now=now)
    customer = await db.scalar(select(User).where(User.email == DEMO_CUSTOMER))
    booker = await db.scalar(select(User).where(User.email.like(f"%{BOOKER_DOMAIN}")))
    screen = await db.scalar(select(Screen).where(Screen.name == "Screen 2"))
    assert customer is not None and booker is not None and screen is not None
    visitor = User(email="real.person@example.in", name="Real Person")
    db.add(visitor)
    await db.flush()
    seats = [s["id"] for s in screen.layout["sections"][0]["rows"][0]["seats"]]

    # neon-alley: only seeded sales and the demo customer's upcoming booking → deleted outright.
    # undertow: a real visitor bought a ticket → the film stays (ended) with just that show.
    morning = (now + timedelta(days=3)).replace(hour=3, minute=0, second=0, microsecond=0)
    gone = await _old_film(db, "neon-alley", screen, morning)
    kept = await _old_film(db, "undertow", screen, morning + timedelta(days=1))
    for show, users in ((gone, [booker, customer]), (kept, [booker, visitor])):
        batch = _Batch(show.id)
        for i, user in enumerate(users):
            batch.order(seats[i * 2 : i * 2 + 2], "classic", 16000, user.id, now)
        await batch.insert(db)
    await db.commit()
    # The demo customer's next booking is the old film's now: they have two upcoming.
    assert len((await my_tickets(db, customer, now=now)).upcoming) == 2

    kept_id = kept.id
    report = await seed(db_engine, now=now)
    assert report["retired_films"] == 2
    db.expire_all()  # the seed ran in its own sessions
    customer = await db.scalar(select(User).where(User.email == DEMO_CUSTOMER))
    visitor = await db.scalar(select(User).where(User.email == "real.person@example.in"))
    assert customer is not None and visitor is not None
    slugs = set(await db.scalars(select(Film.slug).where(Film.slug.in_(RETIRED_FILMS))))
    assert slugs == {"undertow"}
    undertow = await db.scalar(select(Film).where(Film.slug == "undertow"))
    assert undertow is not None and undertow.status == FilmStatus.ENDED
    left = list(await db.scalars(select(Show.id).where(Show.film_id == undertow.id)))
    assert left == [kept_id]
    mine = await my_tickets(db, visitor, now=now)
    assert [t.show.film.slug for t in mine.upcoming] == ["undertow"]

    real = {f.slug for f in FILMS}
    tickets = await my_tickets(db, customer, now=now)
    assert len(tickets.upcoming) == 1 and len(tickets.past) == 1
    assert {t.show.film.slug for t in tickets.upcoming + tickets.past} <= real

    # Nothing left to retire: a third run is a no-op.
    assert (await seed(db_engine, now=now))["retired_films"] == 0
    await demo.ensure_bookings(db, None, customer, now=now)
    assert len((await my_tickets(db, customer, now=now)).upcoming) == 1


async def test_reset(db_engine: AsyncEngine, db: AsyncSession) -> None:
    now = datetime.now(UTC)
    await seed(db_engine, now=now)
    report = await seed(db_engine, now=now, reset=True)
    assert report["new_shows"] > 50
