"""Seed the demo marketplace (R2, B1): `uv run python -m app.seed [--url URL] [--reset]`.

Idempotent and non-destructive — run it any number of times, against a live site too:
- users are upserted by email (demo customer, demo owner, demo staff, `STAFF_EMAILS`, bookers);
- businesses by slug, cinemas by (business, name), screens by (cinema, name) — a screen is
  generated once, so seat ids stay stable (holds and tickets key on them);
- films by slug, with their real release dates (a film is "now showing" from its release date,
  "coming soon" before it); schedules by (screen, film, language, format, times), starting no
  earlier than the film's release;
- shows of current films are never deleted or replaced: the open-ended schedules materialise the
  next 14 days (`schedules.materialise`, the same code a page view runs), so real bookings
  survive a reseed;
- films dropped from the catalogue (`content.RETIRED_FILMS`) are retired: their schedules and
  every show no real visitor has booked go (seeded sales and the demo customer's tickets with
  them, which the seed then rebooks on current films); a film a visitor still holds a ticket for
  stays, ended, so the ticket keeps working.
`--reset` empties every table first (local use).
"""

import argparse
import asyncio
import sys
import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import delete, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.config import get_settings
from app.db import asyncpg_url, make_engine
from app.models import (
    Base,
    Business,
    BusinessMember,
    Cinema,
    Film,
    FilmRequest,
    Order,
    Screen,
    Show,
    ShowPrice,
    ShowSchedule,
    User,
)
from app.models.enums import (
    BusinessStatus,
    Cert,
    FilmStatus,
    OrderStatus,
    RequestStatus,
    ShowStatus,
)
from app.seed import content
from app.seed.content import (
    BUSINESSES,
    FILM_REQUESTS,
    FILMS,
    PAST_BOOKING,
    RETIRED_FILMS,
    RETIRED_REQUESTS,
    BusinessSpec,
)
from app.services import demo
from app.services.schedules import (
    BOOKER_DOMAIN,
    _Batch,
    at_ist,
    clashes,
    ends,
    ist_today,
    materialise,
    occurrences,
)
from app.services.screens import create_screen


class SeedReport(dict[str, int]):
    def __str__(self) -> str:
        return ", ".join(f"{k} {v}" for k, v in self.items())


def check_no_overlap() -> None:
    """Every seeded screen's weekly slots fit without overlapping (a week of occurrences)."""
    runtime = {f.slug: f.runtime_min for f in FILMS}
    monday = date(2026, 11, 2)
    for b in BUSINESSES:
        for c in b.cinemas:
            for s in c.screens:
                starts = sorted(
                    (st, slot.film)
                    for slot in s.slots
                    for st in occurrences(slot.days, slot.times, monday, monday + timedelta(days=7))
                )
                for (a, fa), (z, fz) in zip(starts, starts[1:], strict=False):
                    if clashes(a, ends(a, runtime[fa]), z, ends(z, runtime[fz])):
                        raise ValueError(f"seed slots overlap on {c.name} {s.name}: {fa}/{fz}")


async def seed(
    engine: AsyncEngine, *, now: datetime | None = None, reset: bool = False, staff: str = ""
) -> SeedReport:
    check_no_overlap()
    now = now or datetime.now(UTC)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        if reset:
            tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
            await db.execute(text(f"truncate table {tables} restart identity cascade"))
            await db.commit()
        users = await _users(db, staff)
        retired = await _retire(db, users["customer"])
        films = {spec.slug: await _film(db, spec, now) for spec in FILMS}
        screens: dict[str, Screen] = {}
        businesses: dict[str, Business] = {}
        for spec in BUSINESSES:
            businesses[spec.slug] = await _business(db, spec, users, now)
            for cinema_spec in spec.cinemas:
                cinema = await _cinema(db, businesses[spec.slug], cinema_spec)
                for screen_spec in cinema_spec.screens:
                    screen = await _screen(db, cinema, screen_spec)
                    screens[f"{cinema_spec.name}/{screen_spec.name}"] = screen
                    for slot in screen_spec.slots:
                        await _schedule(db, screen, films[slot.film], slot, screen_spec.prices, now)
        await _requests(db, businesses)
        await db.commit()

        created = await materialise(db, now=now)
        orbit = screens["Orbit Cinemas · Indiranagar/Screen 2"]
        await _past_booking(db, orbit, films, users["customer"], now)
        await demo.ensure_bookings(db, None, users["customer"], now=now)
        shows = await db.scalar(select(Show.id).where(Show.starts_at > now).limit(1))
    return SeedReport(
        users=len(users) + content.BOOKER_COUNT - 1,
        films=len(films),
        retired_films=retired,
        businesses=len(businesses),
        screens=len(screens),
        new_shows=created,
        ok=int(shows is not None),
    )


# --- users ----------------------------------------------------------------------------------------


async def _upsert_user(
    db: AsyncSession, email: str, name: str, *, staff: bool = False, keep_name: bool = False
) -> User:
    user = await db.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(email=email, name=name, is_staff=staff)
        db.add(user)
        await db.flush()
    else:
        if not keep_name:
            user.name = name
        user.is_staff = user.is_staff or staff
    return user


async def _users(db: AsyncSession, staff: str) -> dict[str, User]:
    users = {
        "customer": await _upsert_user(db, content.DEMO_CUSTOMER, "Aarav (demo customer)"),
        "owner": await _upsert_user(db, content.DEMO_OWNER, "Kavitha (Orbit Cinemas demo)"),
        "staff": await _upsert_user(db, content.DEMO_STAFF, "Demo staff", staff=True),
    }
    for spec in BUSINESSES:
        if spec.owner_email != content.DEMO_OWNER:
            users[spec.owner_email] = await _upsert_user(db, spec.owner_email, spec.owner_name)
    for email in (e.strip().lower() for e in staff.split(",")):
        if email:
            users[email] = await _upsert_user(
                db, email, email.split("@")[0].title(), staff=True, keep_name=True
            )
    for i, name in enumerate(content.BOOKER_NAMES[: content.BOOKER_COUNT]):
        await _upsert_user(db, f"booker-{i + 1:02d}{BOOKER_DOMAIN}", name)
    return users


# --- catalogue ------------------------------------------------------------------------------------


async def _film(db: AsyncSession, spec: content.FilmSpec, now: datetime) -> Film:
    film = await db.scalar(select(Film).where(Film.slug == spec.slug))
    if film is None:
        film = Film(slug=spec.slug)
        db.add(film)
    film.title = spec.title
    film.synopsis = spec.synopsis
    film.cast_crew = spec.cast_crew
    film.runtime_min = spec.runtime_min
    film.cert = Cert(spec.cert) if spec.cert else None
    film.genres = spec.genres
    film.languages = spec.languages
    film.formats = spec.formats
    film.poster_url = f"/img/posters/{spec.poster}.png"
    film.banner_url = film.poster_url
    film.trailer_url = None  # no trailer links: the films are real, the studios own them
    film.release_date = spec.release
    film.status = FilmStatus(spec.status(ist_today(now)))
    await db.flush()
    return film


async def _business(
    db: AsyncSession, spec: BusinessSpec, users: dict[str, User], now: datetime
) -> Business:
    business = await db.scalar(select(Business).where(Business.slug == spec.slug))
    if business is None:
        business = Business(
            slug=spec.slug,
            name=spec.name,
            phone=spec.phone,
            status=BusinessStatus(spec.status),
            verified_at=now if spec.status == "verified" else None,
        )
        db.add(business)
        await db.flush()
    business.name, business.phone = spec.name, spec.phone
    if spec.status == "verified" and business.status != BusinessStatus.VERIFIED:
        business.status, business.verified_at = BusinessStatus.VERIFIED, now
    owner = users["owner" if spec.owner_email == content.DEMO_OWNER else spec.owner_email]
    member = await db.get(BusinessMember, (business.id, owner.id))
    if member is None:
        db.add(BusinessMember(business_id=business.id, user_id=owner.id, role="owner"))
    await db.flush()
    return business


async def _cinema(db: AsyncSession, business: Business, spec: content.CinemaSpec) -> Cinema:
    cinema = await db.scalar(
        select(Cinema).where(Cinema.business_id == business.id, Cinema.name == spec.name)
    )
    if cinema is None:
        cinema = Cinema(business_id=business.id, name=spec.name)
        db.add(cinema)
    cinema.area, cinema.address = spec.area, spec.address
    cinema.facilities = spec.facilities
    cinema.photo_url = f"/img/cinemas/{spec.photo}.jpg" if spec.photo else None
    await db.flush()
    return cinema


async def _screen(db: AsyncSession, cinema: Cinema, spec: content.ScreenSpec) -> Screen:
    screen = await db.scalar(
        select(Screen).where(Screen.cinema_id == cinema.id, Screen.name == spec.name)
    )
    if screen is None:
        screen = await create_screen(
            db, cinema.id, name=spec.name, formats=spec.formats, knobs=spec.knobs
        )
    screen.formats = spec.formats
    await db.flush()
    return screen


async def _schedule(
    db: AsyncSession,
    screen: Screen,
    film: Film,
    slot: content.Slot,
    prices: dict[str, int],
    now: datetime,
) -> None:
    times = sorted(slot.times)
    # A coming-soon film's shows start on its release date.
    first = max(ist_today(now), film.release_date)
    existing = await db.scalar(
        select(ShowSchedule).where(
            ShowSchedule.screen_id == screen.id,
            ShowSchedule.film_id == film.id,
            ShowSchedule.language == slot.language,
            ShowSchedule.format == slot.format,
            ShowSchedule.times == times,
            ShowSchedule.to_date.is_(None),
        )
    )
    if existing is None:
        existing = ShowSchedule(
            screen_id=screen.id,
            film_id=film.id,
            language=slot.language,
            format=slot.format,
            times=times,
            from_date=first,
        )
        db.add(existing)
    elif existing.from_date < film.release_date:  # the release moved later
        existing.from_date = film.release_date
    existing.days_of_week = sorted(slot.days)
    existing.prices = prices
    existing.seed_fill = slot.fill or None
    await db.flush()


async def _retire(db: AsyncSession, customer: User) -> int:
    """Take the films in `RETIRED_FILMS` out of the catalogue. A show is kept only while a real
    visitor (not a seeded booker, not the demo customer) has a live order for it; everything
    else of the film goes, and the film itself too unless such a show is left (then it's ended).
    Returns how many films were retired; 0 once they're gone, so re-running is a no-op."""
    films = list(
        await db.scalars(
            select(Film).where(Film.slug.in_(RETIRED_FILMS), Film.status != FilmStatus.ENDED)
        )
    )
    if not films:
        return 0
    seeded = select(User.id).where(
        or_(User.email.like(f"%{BOOKER_DOMAIN}"), User.id == customer.id)
    )
    visitors = select(Order.show_id).where(
        Order.status.in_([OrderStatus.PAID, OrderStatus.PENDING]),
        or_(Order.user_id.is_(None), Order.user_id.not_in(seeded)),
    )
    for film in films:
        await db.execute(delete(ShowSchedule).where(ShowSchedule.film_id == film.id))
        # Orders, tickets and prices go with their show (ON DELETE CASCADE).
        await db.execute(delete(Show).where(Show.film_id == film.id, Show.id.not_in(visitors)))
        kept = await db.scalar(
            select(func.count()).select_from(Show).where(Show.film_id == film.id)
        )
        if kept:
            film.status = FilmStatus.ENDED
        else:
            await db.execute(delete(Film).where(Film.id == film.id))
    await db.execute(
        delete(FilmRequest).where(
            FilmRequest.title.in_(RETIRED_REQUESTS), FilmRequest.status == RequestStatus.OPEN
        )
    )
    await db.commit()
    return len(films)


async def _requests(db: AsyncSession, businesses: dict[str, Business]) -> None:
    for slug, title, note in FILM_REQUESTS:
        business = businesses[slug]
        found = await db.scalar(
            select(FilmRequest.id).where(
                FilmRequest.business_id == business.id, FilmRequest.title == title
            )
        )
        if found is None:
            db.add(
                FilmRequest(
                    business_id=business.id, title=title, note=note, status=RequestStatus.OPEN
                )
            )
    await db.flush()


async def _past_booking(
    db: AsyncSession, screen: Screen, films: dict[str, Film], customer: User, now: datetime
) -> None:
    """One booking the demo customer has already watched (scanned in), so My tickets has a
    "past" side. Made once; it stays in the past for ever."""
    if await db.scalar(
        select(Order.id)
        .join(Show, Show.id == Order.show_id)
        .where(Order.user_id == customer.id, Order.status == OrderStatus.PAID, Show.ends_at < now)
        .limit(1)
    ):
        return
    slug, days_ago, at, tier, count = PAST_BOOKING
    film = films[slug]
    starts = at_ist(ist_today(now) - timedelta(days=days_ago), at)
    show = Show(
        id=uuid.uuid4(),
        screen_id=screen.id,
        film_id=film.id,
        language=film.languages[0],
        format="2D",
        starts_at=starts,
        ends_at=ends(starts, film.runtime_min),
        status=ShowStatus.SCHEDULED,
    )
    db.add(show)
    await db.flush()
    prices = {"classic": 16000, "prime": 22000}
    db.add_all(ShowPrice(show_id=show.id, tier_key=k, price_paise=p) for k, p in prices.items())
    pair = demo.centre_pair(screen, tier, set(), count)
    assert pair is not None
    batch = _Batch(show.id)
    batch.order(pair, tier, prices[tier], customer.id, starts - timedelta(days=2), "UPI")
    for t in batch.tickets:
        t["checked_in_at"] = starts - timedelta(minutes=12)
    await batch.insert(db)
    await db.commit()


# --- CLI ------------------------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])  # type: ignore[union-attr]
    parser.add_argument("--url", help="asyncpg URL; default DATABASE_URL from api/.env.local")
    parser.add_argument("--reset", action="store_true", help="empty every table first (local)")
    args = parser.parse_args(argv)
    settings = get_settings()
    url = args.url
    if not url:
        if settings.database_url is None:
            raise SystemExit("Set DATABASE_URL (api/.env.local) or pass --url")
        url = settings.database_url.get_secret_value()

    async def run() -> SeedReport:
        engine = make_engine(asyncpg_url(url))
        try:
            return await seed(engine, reset=args.reset, staff=settings.staff_emails)
        finally:
            await engine.dispose()

    print(f"seeded: {asyncio.run(run())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
