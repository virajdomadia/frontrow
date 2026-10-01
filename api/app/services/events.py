"""Public catalog reads: events list with URL filters, event page with showtimes, home strip.

One query loads every upcoming showtime (scheduled, in the future) with its venue, fill and
price range; the list/facets are then grouped in Python — the catalog is tens of events and a
few hundred showtimes, so this stays simpler and cheaper than four aggregate queries.
"""

from __future__ import annotations

import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import Integer, Uuid, column, func, select, table
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import ApiError
from app.models import Event, PriceTier, Showtime, Venue
from app.models.enums import EventStatus, ShowtimeStatus
from app.schemas.events import (
    EventCard,
    EventDetail,
    EventList,
    FilterOption,
    Home,
    NextShowtime,
    ShowtimeSummary,
    TierPrice,
    VenueRef,
)

IST = ZoneInfo("Asia/Kolkata")
FILLING_AT = 0.75  # share sold at which the badge says "filling fast" (04 §3; F3 adds holds)
HOME_COUNT = 6

# The `showtime_fill` view from 0001_v1 (06 §A) — sold seats per showtime.
showtime_fill = table(
    "showtime_fill",
    column("showtime_id", Uuid),
    column("seat_count", Integer),
    column("sold", Integer),
)


@dataclass(frozen=True)
class ListParams:
    date: str | None = None  # today | tomorrow | weekend | YYYY-MM-DD
    type: str | None = None  # movie | concert
    genre: str | None = None
    venue: uuid.UUID | None = None
    sort: str = "soonest"


@dataclass
class ShowtimeRow:
    id: uuid.UUID
    event_id: uuid.UUID
    starts_at: datetime
    venue: VenueRef
    seat_count: int
    sold: int
    price_min: int
    price_max: int

    @property
    def fill(self) -> str:
        if self.sold >= self.seat_count:
            return "sold_out"
        return "filling" if self.sold >= self.seat_count * FILLING_AT else "available"


# --- date windows ---------------------------------------------------------------------------------


def date_window(preset: str | None, now: datetime) -> tuple[datetime, datetime | None]:
    """`(start, end)` in UTC for a date filter; end None = open-ended. Presets are IST days."""
    local = now.astimezone(IST)
    today = local.date()
    if preset is None:
        return now, None
    if preset == "today":
        return now, _day_end(today)
    if preset == "tomorrow":
        return _day_start(today + timedelta(days=1)), _day_end(today + timedelta(days=1))
    if preset == "weekend":
        # Saturday + Sunday of this week; from now if the weekend has started.
        saturday = today + timedelta(days=(5 - today.weekday()) % 7)
        if today.weekday() == 6:
            saturday = today - timedelta(days=1)
        return max(now, _day_start(saturday)), _day_end(saturday + timedelta(days=1))
    try:
        day = date.fromisoformat(preset)
    except ValueError as e:
        raise ApiError(
            "validation",
            "date must be today, tomorrow, weekend or YYYY-MM-DD",
            details={"fields": {"date": "invalid"}},
        ) from e
    return max(now, _day_start(day)), _day_end(day)


def _day_start(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=IST)


def _day_end(day: date) -> datetime:
    return _day_start(day + timedelta(days=1))


# --- loading --------------------------------------------------------------------------------------


async def load_showtimes(
    db: AsyncSession,
    *,
    now: datetime,
    start: datetime | None = None,
    end: datetime | None = None,
    event_ids: list[uuid.UUID] | None = None,
) -> list[ShowtimeRow]:
    prices = (
        select(
            PriceTier.showtime_id,
            func.min(PriceTier.price_paise).label("price_min"),
            func.max(PriceTier.price_paise).label("price_max"),
        )
        .group_by(PriceTier.showtime_id)
        .subquery()
    )
    q = (
        select(
            Showtime.id,
            Showtime.event_id,
            Showtime.starts_at,
            Venue.id.label("venue_id"),
            Venue.name,
            Venue.address,
            Venue.photo_url,
            Venue.seat_count,
            showtime_fill.c.sold,
            prices.c.price_min,
            prices.c.price_max,
        )
        .join(Venue, Venue.id == Showtime.venue_id)
        .join(showtime_fill, showtime_fill.c.showtime_id == Showtime.id)
        .join(prices, prices.c.showtime_id == Showtime.id)
        .where(Showtime.status == ShowtimeStatus.SCHEDULED, Showtime.starts_at > (start or now))
        .order_by(Showtime.starts_at)
    )
    if end is not None:
        q = q.where(Showtime.starts_at < end)
    if event_ids is not None:
        q = q.where(Showtime.event_id.in_(event_ids))
    rows = (await db.execute(q)).all()
    return [
        ShowtimeRow(
            id=r.id,
            event_id=r.event_id,
            starts_at=r.starts_at,
            venue=VenueRef(
                id=r.venue_id,
                name=r.name,
                address=r.address,
                seat_count=r.seat_count,
                photo_url=r.photo_url,
            ),
            seat_count=r.seat_count,
            sold=r.sold,
            price_min=r.price_min,
            price_max=r.price_max,
        )
        for r in rows
    ]


def card(event: Event, showtimes: list[ShowtimeRow]) -> EventCard:
    """`showtimes` = this event's upcoming showtimes in the list's window, soonest first."""
    nxt = showtimes[0] if showtimes else None
    return EventCard(
        id=event.id,
        slug=event.slug,
        title=event.title,
        type=event.type.value,  # type: ignore[arg-type]
        genre=event.genre,
        rating=event.rating,
        duration_min=event.duration_min,
        poster_url=event.poster_url,
        from_price_paise=min((s.price_min for s in showtimes), default=None),
        next_showtime=nxt
        and NextShowtime(
            id=nxt.id,
            starts_at=nxt.starts_at,
            venue_name=nxt.venue.name,
            fill=nxt.fill,  # type: ignore[arg-type]
        ),
        upcoming_count=len(showtimes),
    )


# --- reads ----------------------------------------------------------------------------------------


async def list_events(db: AsyncSession, params: ListParams, *, now: datetime) -> EventList:
    start, end = date_window(params.date, now)
    events = list(await db.scalars(select(Event).where(Event.status == EventStatus.LIVE)))
    by_event: dict[uuid.UUID, list[ShowtimeRow]] = defaultdict(list)
    for s in await load_showtimes(db, now=now, start=start, end=end):
        by_event[s.event_id].append(s)

    # Facets count over the date window only, so a chip never leads to an empty page.
    live = [e for e in events if by_event[e.id]]
    genre_counts = Counter(e.genre for e in live)
    venue_counts: Counter[tuple[uuid.UUID, str]] = Counter()
    for e in live:
        for v in {(s.venue.id, s.venue.name) for s in by_event[e.id]}:
            venue_counts[v] += 1

    chosen = [
        e
        for e in live
        if (params.type is None or e.type.value == params.type)
        and (params.genre is None or e.genre.lower() == params.genre.lower())
    ]
    cards: list[EventCard] = []
    showtime_count = 0
    for e in chosen:
        shows = by_event[e.id]
        if params.venue is not None:
            shows = [s for s in shows if s.venue.id == params.venue]
            if not shows:
                continue
        showtime_count += len(shows)
        cards.append(card(e, shows))
    cards.sort(key=_sort_key(params.sort))
    return EventList(
        events=cards,
        total=len(cards),
        showtime_count=showtime_count,
        genres=[FilterOption(value=g, label=g, count=n) for g, n in sorted(genre_counts.items())],
        venues=[
            FilterOption(value=str(vid), label=name, count=n)
            for (vid, name), n in sorted(venue_counts.items(), key=lambda kv: kv[0][1])
        ],
    )


def _sort_key(sort: str):  # type: ignore[no-untyped-def]
    far = datetime.max.replace(tzinfo=IST)
    if sort == "price":
        return lambda c: (c.from_price_paise is None, c.from_price_paise or 0, c.title)
    if sort == "title":
        return lambda c: c.title.lower()
    return lambda c: (c.next_showtime.starts_at if c.next_showtime else far, c.title)


async def get_event(db: AsyncSession, slug: str, *, now: datetime) -> EventDetail:
    event = await db.scalar(
        select(Event).where(Event.slug == slug, Event.status == EventStatus.LIVE)
    )
    if event is None:
        raise ApiError("not_found", "No such event")
    shows = await load_showtimes(db, now=now, event_ids=[event.id])
    tiers = (
        await db.execute(
            select(PriceTier)
            .where(PriceTier.showtime_id.in_([s.id for s in shows]))
            .order_by(PriceTier.price_paise)
        )
    ).scalars()
    tiers_by_showtime: dict[uuid.UUID, list[TierPrice]] = defaultdict(list)
    for t in tiers:
        tiers_by_showtime[t.showtime_id].append(
            TierPrice(tier_key=t.tier_key, label=t.label, price_paise=t.price_paise)
        )
    base = card(event, shows)
    return EventDetail(
        **base.model_dump(),
        synopsis=event.synopsis,
        cast_lineup=event.cast_lineup,
        gallery_urls=event.gallery_urls,
        showtimes=[
            ShowtimeSummary(
                id=s.id,
                starts_at=s.starts_at,
                venue=s.venue,
                tiers=tiers_by_showtime[s.id],
                price_min_paise=s.price_min,
                price_max_paise=s.price_max,
                fill=s.fill,  # type: ignore[arg-type]
                seats_left=s.seat_count - s.sold,
            )
            for s in shows
        ],
    )


async def home(db: AsyncSession, *, now: datetime) -> Home:
    """The landing strip: the six events with the soonest upcoming showtime."""
    listing = await list_events(db, ListParams(), now=now)
    return Home(now_showing=listing.events[:HOME_COUNT])
