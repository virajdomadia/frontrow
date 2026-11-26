"""Public catalogue reads (R3, R4): home, film search, the movie page and its showtimes.

A show is bookable when it is scheduled, hasn't started, sits within the 14-day horizon, its
film is now showing and its business is verified. Every read first makes sure the open-ended
schedules have their next 14 days of shows (`schedules.materialise`, a no-op almost always).

One query loads the bookable shows with screen, cinema, fill and price range; grouping happens in
Python — the catalogue is tens of films and a few hundred shows.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from redis.asyncio import Redis
from sqlalchemy import Integer, Uuid, column, func, or_, select, table
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import ApiError
from app.models import Business, Cinema, Film, Screen, Show, ShowPrice
from app.models.enums import BusinessStatus, FilmStatus, ShowStatus
from app.schemas.catalog import (
    CastMember,
    CinemaShows,
    DateOption,
    FilmCard,
    FilmDetail,
    FilmList,
    FilmShows,
    Home,
    ShowSlot,
    TierPrice,
    Version,
)
from app.services import holds
from app.services.schedules import HORIZON_DAYS, IST, ist_today, materialise

FILLING_AT = 0.7  # share held + sold at which a time turns "filling fast" (R4)
DATE_STRIP = 7

# The `show_fill` view (0002): sold seats per show.
show_fill = table(
    "show_fill", column("show_id", Uuid), column("seat_count", Integer), column("sold", Integer)
)


def fill_of(seat_count: int, sold: int, held: int = 0) -> str:
    """Sold out is sales only (holds lapse); "filling fast" counts live holds too."""
    if sold >= seat_count:
        return "sold_out"
    return "filling" if sold + held >= seat_count * FILLING_AT else "available"


@dataclass
class Slot:
    id: uuid.UUID
    film_id: uuid.UUID
    starts_at: datetime
    language: str
    format: str
    screen_name: str
    cinema_id: uuid.UUID
    seat_count: int
    sold: int
    held: int = 0
    tiers: list[TierPrice] = field(default_factory=list)

    @property
    def fill(self) -> str:
        return fill_of(self.seat_count, self.sold, self.held)

    @property
    def seats_left(self) -> int:
        return max(self.seat_count - self.sold - self.held, 0)

    @property
    def price_min(self) -> int | None:
        return min((t.price_paise for t in self.tiers), default=None)


def bookable(now: datetime):  # type: ignore[no-untyped-def]
    """The WHERE clause every public show read shares."""
    return (
        Show.status == ShowStatus.SCHEDULED,
        Show.starts_at > now,
        Show.starts_at < now + timedelta(days=HORIZON_DAYS),
        Film.status == FilmStatus.NOW_SHOWING,
        Business.status == BusinessStatus.VERIFIED,
    )


async def load_slots(
    db: AsyncSession,
    *,
    now: datetime,
    film_ids: list[uuid.UUID] | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    redis: Redis | None = None,
    with_cinemas: dict[uuid.UUID, Cinema] | None = None,
) -> list[Slot]:
    q = (
        select(
            Show.id,
            Show.film_id,
            Show.starts_at,
            Show.language,
            Show.format,
            Screen.name,
            Screen.tiers,
            Cinema.id,
            show_fill.c.seat_count,
            show_fill.c.sold,
        )  # fmt: skip
        .join(Film, Film.id == Show.film_id)
        .join(Screen, Screen.id == Show.screen_id)
        .join(Cinema, Cinema.id == Screen.cinema_id)
        .join(Business, Business.id == Cinema.business_id)
        .join(show_fill, show_fill.c.show_id == Show.id)
        .where(*bookable(now))
        .order_by(Show.starts_at, Cinema.name)
    )
    if film_ids is not None:
        q = q.where(Show.film_id.in_(film_ids))
    if start is not None:
        q = q.where(Show.starts_at >= start)
    if end is not None:
        q = q.where(Show.starts_at < end)
    rows = (await db.execute(q)).all()
    labels: dict[uuid.UUID, dict[str, str]] = {}
    slots: list[Slot] = []
    for r in rows:
        (sid, fid, starts, lang, fmt, screen_name, tiers, cinema_id, seats, sold) = r._tuple()
        labels[sid] = {t["key"]: t["label"] for t in tiers}
        slots.append(Slot(sid, fid, starts, lang, fmt, screen_name, cinema_id, seats, sold))
    if slots:
        ids = [s.id for s in slots]
        prices: dict[uuid.UUID, list[ShowPrice]] = defaultdict(list)
        for p in await db.scalars(
            select(ShowPrice).where(ShowPrice.show_id.in_(ids)).order_by(ShowPrice.price_paise)
        ):
            prices[p.show_id].append(p)
        held = await holds.held_counts(redis, ids)
        for s in slots:
            s.held = held.get(s.id, 0)
            s.tiers = [
                TierPrice(tier_key=p.tier_key, label=labels[s.id].get(p.tier_key, p.tier_key),
                          price_paise=p.price_paise)
                for p in prices[s.id]
            ]  # fmt: skip
    return slots


def card(film: Film, slots: list[Slot]) -> FilmCard:
    return FilmCard(
        id=film.id,
        slug=film.slug,
        title=film.title,
        cert=film.cert.value,  # type: ignore[arg-type]
        runtime_min=film.runtime_min,
        genres=list(film.genres),
        languages=list(film.languages),
        formats=list(film.formats),
        poster_url=film.poster_url,
        banner_url=film.banner_url,
        status=film.status.value,  # type: ignore[arg-type]
        release_date=film.release_date,
        show_count=len(slots),
        from_price_paise=min((p for s in slots if (p := s.price_min) is not None), default=None),
    )


def _versions(slots: list[Slot]) -> list[Version]:
    counts: dict[tuple[str, str], int] = defaultdict(int)
    for s in slots:
        counts[(s.language, s.format)] += 1
    return [
        Version(language=lang, format=fmt, show_count=n)
        for (lang, fmt), n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    ]


# --- reads ----------------------------------------------------------------------------------------


async def home(db: AsyncSession, *, now: datetime, redis: Redis | None = None) -> Home:
    await materialise(db, now=now)
    films = list(
        await db.scalars(
            select(Film)
            .where(Film.status.in_([FilmStatus.NOW_SHOWING, FilmStatus.COMING_SOON]))
            .order_by(Film.release_date.desc(), Film.title)
        )
    )
    by_film: dict[uuid.UUID, list[Slot]] = defaultdict(list)
    for s in await load_slots(db, now=now, redis=redis):
        by_film[s.film_id].append(s)
    now_showing = [
        card(f, by_film[f.id])
        for f in films
        if f.status == FilmStatus.NOW_SHOWING and by_film[f.id]
    ]
    now_showing.sort(key=lambda c: -c.show_count)
    coming = [card(f, []) for f in films if f.status == FilmStatus.COMING_SOON]
    coming.sort(key=lambda c: c.release_date)
    return Home(now_showing=now_showing, coming_soon=coming)


async def search(
    db: AsyncSession, q: str | None, *, now: datetime, redis: Redis | None = None
) -> FilmList:
    await materialise(db, now=now)
    stmt = select(Film).where(Film.status.in_([FilmStatus.NOW_SHOWING, FilmStatus.COMING_SOON]))
    term = (q or "").strip()
    if term:
        like = f"%{term.replace('%', '').replace('_', '')}%"
        stmt = stmt.where(
            or_(Film.title.ilike(like), func.array_to_string(Film.genres, " ").ilike(like))
        )
    films = list(await db.scalars(stmt.order_by(Film.title)))
    by_film: dict[uuid.UUID, list[Slot]] = defaultdict(list)
    if films:
        for s in await load_slots(db, now=now, film_ids=[f.id for f in films], redis=redis):
            by_film[s.film_id].append(s)
    cards = [card(f, by_film[f.id]) for f in films]
    cards.sort(key=lambda c: (c.status != "now_showing", -c.show_count, c.title))
    return FilmList(films=cards, q=term or None)


async def _film(db: AsyncSession, slug: str) -> Film:
    film = await db.scalar(select(Film).where(Film.slug == slug))
    if film is None:
        raise ApiError("not_found", "No such film")
    return film


async def film_detail(
    db: AsyncSession, slug: str, *, now: datetime, redis: Redis | None = None
) -> FilmDetail:
    await materialise(db, now=now)
    film = await _film(db, slug)
    slots = await load_slots(db, now=now, film_ids=[film.id], redis=redis)
    return FilmDetail(
        **card(film, slots).model_dump(),
        synopsis=film.synopsis,
        cast_crew=[CastMember(**c) for c in film.cast_crew],
        trailer_url=film.trailer_url,
        versions=_versions(slots),
    )


def _day_bounds(day: date) -> tuple[datetime, datetime]:
    start = datetime.combine(day, datetime.min.time(), tzinfo=IST)
    return start, start + timedelta(days=1)


async def film_shows(
    db: AsyncSession,
    slug: str,
    *,
    day: date | None,
    language: str | None,
    format: str | None,
    now: datetime,
    redis: Redis | None = None,
) -> FilmShows:
    """Showtimes for one film, version and day, grouped by cinema (R4). With no version given,
    the one with the most shows; with no day, the first day that has any."""
    await materialise(db, now=now)
    film = await _film(db, slug)
    all_slots = await load_slots(db, now=now, film_ids=[film.id], redis=redis)
    versions = _versions(all_slots)
    if language is None and format is None and versions:
        language, format = versions[0].language, versions[0].format
    chosen = [
        s
        for s in all_slots
        if (language is None or s.language == language) and (format is None or s.format == format)
    ]
    today = ist_today(now)
    strip = [today + timedelta(days=i) for i in range(DATE_STRIP)]
    per_day: dict[date, int] = defaultdict(int)
    for s in chosen:
        per_day[s.starts_at.astimezone(IST).date()] += 1
    if day is None:
        day = next((d for d in strip if per_day[d]), today)
    lo, hi = _day_bounds(day)
    todays = [s for s in chosen if lo <= s.starts_at < hi]

    cinema_ids = list(dict.fromkeys(s.cinema_id for s in todays))
    cinemas = (
        {c.id: c for c in await db.scalars(select(Cinema).where(Cinema.id.in_(cinema_ids)))}
        if cinema_ids
        else {}
    )
    grouped: dict[uuid.UUID, list[ShowSlot]] = defaultdict(list)
    for s in todays:
        grouped[s.cinema_id].append(
            ShowSlot(
                id=s.id,
                starts_at=s.starts_at,
                screen_name=s.screen_name,
                language=s.language,
                format=s.format,
                fill=s.fill,  # type: ignore[arg-type]
                seats_left=s.seats_left,
                tiers=s.tiers,
            )
        )
    out = [
        CinemaShows(
            id=c.id,
            name=c.name,
            area=c.area,
            address=c.address,
            facilities=list(c.facilities),
            shows=grouped[c.id],
        )
        for c in sorted(cinemas.values(), key=lambda c: c.name)
    ]
    return FilmShows(
        film=card(film, all_slots),
        language=language,
        format=format,
        versions=versions,
        date=day,
        dates=[DateOption(date=d, show_count=per_day[d]) for d in strip],
        cinemas=out,
    )
