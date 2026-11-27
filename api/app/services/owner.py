"""Theatre owner console (R8–R10): business, cinemas, screens, film requests, bulk scheduling,
shows by day, bookings + CSV, and the door.

Everything is scoped to the caller's business: another business's cinema, screen or show simply
doesn't exist (404), so ids can't be probed. A business can build everything while it is pending
verification; nothing is public until staff approve it.
"""

from __future__ import annotations

import csv
import io
import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.errors import ApiError
from app.models import (
    Business,
    Cinema,
    Film,
    FilmRequest,
    Order,
    OrderSeat,
    Screen,
    Seat,
    Show,
    ShowSchedule,
    Ticket,
    User,
)
from app.models.enums import BusinessStatus, FilmStatus, OrderStatus, RequestStatus, ShowStatus
from app.schemas.layouts import LayoutTier
from app.schemas.owner import (
    Booking,
    Bookings,
    BulkResult,
    BulkShows,
    BusinessPatch,
    CheckInResult,
    CinemaIn,
    DayCount,
    FilmRef,
    FilmRequestIn,
    OwnerBusiness,
    OwnerCinema,
    OwnerFilmRequest,
    OwnerScreen,
    OwnerScreenDetail,
    OwnerShow,
    OwnerShows,
    ScreenIn,
    ShowFilmRef,
)
from app.services import tickets as tokens
from app.services.orders import seat_label
from app.services.schedules import (
    IST,
    busy_on_screen,
    clashes,
    ends,
    ist_today,
    materialise_schedule,
    occurrences,
    planned_minutes,
)
from app.services.screens import create_screen
from app.services.shows import parse_id

MAX_RANGE_DAYS = 60


def _pairs(result) -> dict:  # type: ignore[no-untyped-def]
    return {k: v for k, v in result.tuples()}


# --- business -------------------------------------------------------------------------------------


async def _upcoming_by_screen(
    db: AsyncSession, screen_ids: list[uuid.UUID], now: datetime
) -> dict[uuid.UUID, int]:
    if not screen_ids:
        return {}
    return _pairs(
        await db.execute(
            select(Show.screen_id, func.count())
            .where(
                Show.screen_id.in_(screen_ids),
                Show.starts_at > now,
                Show.status == ShowStatus.SCHEDULED,
            )
            .group_by(Show.screen_id)
        )
    )


async def business_out(db: AsyncSession, business: Business, now: datetime) -> OwnerBusiness:
    cinemas = list(await db.scalars(select(Cinema.id).where(Cinema.business_id == business.id)))
    screens = (
        list(await db.scalars(select(Screen.id).where(Screen.cinema_id.in_(cinemas))))
        if cinemas
        else []
    )
    upcoming = await _upcoming_by_screen(db, screens, now)
    return OwnerBusiness(
        id=business.id,
        name=business.name,
        slug=business.slug,
        phone=business.phone,
        status=business.status.value,  # type: ignore[arg-type]
        review_note=business.review_note,
        created_at=business.created_at,
        verified_at=business.verified_at,
        cinema_count=len(cinemas),
        screen_count=len(screens),
        upcoming_shows=sum(upcoming.values()),
    )


async def patch_business(
    db: AsyncSession, business: Business, body: BusinessPatch, now: datetime
) -> OwnerBusiness:
    business.name = body.name.strip()
    business.phone = body.phone.strip()
    if business.status == BusinessStatus.REJECTED:
        business.status = BusinessStatus.PENDING  # back into the approvals queue
        business.review_note = None
    await db.commit()
    return await business_out(db, business, now)


# --- cinemas + screens ----------------------------------------------------------------------------


def screen_out(s: Screen, upcoming: int) -> OwnerScreen:
    return OwnerScreen(
        id=s.id,
        cinema_id=s.cinema_id,
        name=s.name,
        template=s.template.value,  # type: ignore[arg-type]
        seat_count=s.seat_count,
        formats=list(s.formats),
        tiers=[LayoutTier(**t) for t in s.tiers],
        upcoming_shows=upcoming,
    )


async def list_cinemas(db: AsyncSession, business: Business, now: datetime) -> list[OwnerCinema]:
    cinemas = list(
        await db.scalars(
            select(Cinema).where(Cinema.business_id == business.id).order_by(Cinema.created_at)
        )
    )
    screens: dict[uuid.UUID, list[Screen]] = defaultdict(list)
    if cinemas:
        for s in await db.scalars(
            select(Screen)
            .where(Screen.cinema_id.in_([c.id for c in cinemas]))
            .order_by(Screen.created_at)
        ):
            screens[s.cinema_id].append(s)
    upcoming = await _upcoming_by_screen(
        db, [s.id for group in screens.values() for s in group], now
    )
    return [
        OwnerCinema(
            id=c.id,
            name=c.name,
            area=c.area,
            address=c.address,
            facilities=list(c.facilities),
            photo_url=c.photo_url,
            screens=[screen_out(s, upcoming.get(s.id, 0)) for s in screens[c.id]],
            upcoming_shows=sum(upcoming.get(s.id, 0) for s in screens[c.id]),
            created_at=c.created_at,
        )
        for c in cinemas
    ]


async def own_cinema(db: AsyncSession, business: Business, cinema_id: str | uuid.UUID) -> Cinema:
    cinema = await db.get(Cinema, parse_id(cinema_id, "cinema"))
    if cinema is None or cinema.business_id != business.id:
        raise ApiError("not_found", "No such cinema")
    return cinema


async def cinema_out(
    db: AsyncSession, business: Business, cinema_id: uuid.UUID, now: datetime
) -> OwnerCinema:
    for c in await list_cinemas(db, business, now):
        if c.id == cinema_id:
            return c
    raise ApiError("not_found", "No such cinema")


async def save_cinema(
    db: AsyncSession,
    business: Business,
    body: CinemaIn,
    now: datetime,
    *,
    cinema_id: str | None = None,
) -> OwnerCinema:
    name = body.name.strip()
    clash = await db.scalar(
        select(Cinema.id).where(
            Cinema.business_id == business.id,
            func.lower(Cinema.name) == name.lower(),
            *([Cinema.id != parse_id(cinema_id, "cinema")] if cinema_id else []),
        )
    )
    if clash:
        raise ApiError(
            "conflict",
            "You already have a cinema with this name",
            details={"fields": {"name": "taken"}},
        )
    if cinema_id is None:
        cinema = Cinema(business_id=business.id, name=name)
        db.add(cinema)
    else:
        cinema = await own_cinema(db, business, cinema_id)
        cinema.name = name
    cinema.area = body.area.strip()
    cinema.address = body.address.strip()
    cinema.facilities = list(dict.fromkeys(body.facilities))
    cinema.photo_url = body.photo_url
    await db.commit()
    return await cinema_out(db, business, cinema.id, now)


async def own_screen(db: AsyncSession, business: Business, screen_id: str | uuid.UUID) -> Screen:
    row = (
        await db.execute(
            select(Screen, Cinema)
            .join(Cinema, Cinema.id == Screen.cinema_id)
            .where(Screen.id == parse_id(screen_id, "screen"))
        )
    ).one_or_none()
    if row is None or row[1].business_id != business.id:
        raise ApiError("not_found", "No such screen")
    return row[0]


async def add_screen(
    db: AsyncSession, business: Business, cinema_id: str, body: ScreenIn, now: datetime
) -> OwnerScreen:
    cinema = await own_cinema(db, business, cinema_id)
    name = body.name.strip()
    if await db.scalar(
        select(Screen.id).where(
            Screen.cinema_id == cinema.id, func.lower(Screen.name) == name.lower()
        )
    ):
        raise ApiError(
            "conflict",
            "This cinema already has a screen with this name",
            details={"fields": {"name": "taken"}},
        )
    screen = await create_screen(
        db, cinema.id, name=name, formats=list(body.formats), knobs=body.knobs
    )
    await db.commit()
    return screen_out(screen, 0)


async def screen_detail(
    db: AsyncSession, business: Business, screen_id: str, now: datetime
) -> OwnerScreenDetail:
    s = await own_screen(db, business, screen_id)
    base = screen_out(s, (await _upcoming_by_screen(db, [s.id], now)).get(s.id, 0))
    return OwnerScreenDetail(**base.model_dump(), knobs=s.knobs, layout=s.layout)  # type: ignore[arg-type]


# --- film requests --------------------------------------------------------------------------------


async def list_requests(db: AsyncSession, business: Business) -> list[OwnerFilmRequest]:
    rows = await db.execute(
        select(FilmRequest, Film)
        .outerjoin(Film, Film.id == FilmRequest.film_id)
        .where(FilmRequest.business_id == business.id)
        .order_by(FilmRequest.created_at.desc())
    )
    return [
        OwnerFilmRequest(
            id=r.id,
            title=r.title,
            note=r.note,
            status=r.status.value,  # type: ignore[arg-type]
            reply=r.reply,
            film=FilmRef(id=f.id, slug=f.slug, title=f.title) if f else None,
            created_at=r.created_at,
        )
        for r, f in rows.tuples()
    ]


async def request_film(
    db: AsyncSession, business: Business, body: FilmRequestIn
) -> OwnerFilmRequest:
    title = body.title.strip()
    existing = await db.scalar(
        select(Film).where(func.lower(Film.title) == title.lower(), Film.status != FilmStatus.ENDED)
    )
    if existing is not None:
        raise ApiError(
            "conflict",
            f"“{existing.title}” is already in the catalogue — schedule it directly.",
            details={"film": {"id": str(existing.id), "slug": existing.slug}},
        )
    req = FilmRequest(
        business_id=business.id, title=title, note=(body.note or "").strip() or None,
        status=RequestStatus.OPEN,
    )  # fmt: skip
    db.add(req)
    await db.commit()
    return (await list_requests(db, business))[0]


# --- shows ----------------------------------------------------------------------------------------


def _bad(field: str, message: str) -> ApiError:
    return ApiError("validation", message, details={"fields": {field: message}})


async def bulk_schedule(
    db: AsyncSession, business: Business, body: BulkShows, now: datetime
) -> BulkResult:
    """Validate the whole batch, refuse any overlap (naming the clashing show), then create the
    schedule and every show at once."""
    screen = await own_screen(db, business, body.screen_id)
    # Serialise scheduling per screen, so two owners' tabs can't both pass the overlap check.
    await db.execute(select(Screen.id).where(Screen.id == screen.id).with_for_update())
    film = await db.get(Film, body.film_id)
    if film is None:
        raise ApiError("not_found", "No such film")
    if film.status == FilmStatus.ENDED:
        raise _bad("film_id", "This film has ended and takes no new shows")
    if body.language not in film.languages:
        raise _bad("language", f"{film.title} isn't available in {body.language}")
    if body.format not in film.formats:
        raise _bad("format", f"{film.title} isn't released in {body.format}")
    if body.format not in screen.formats:
        raise _bad("format", f"{screen.name} can't play {body.format}")
    today = ist_today(now)
    if body.from_date < today:
        raise _bad("from_date", "Start today or later")
    if body.to_date < body.from_date:
        raise _bad("to_date", "The end date is before the start date")
    if (body.to_date - body.from_date).days >= MAX_RANGE_DAYS:
        raise _bad("to_date", f"Schedule up to {MAX_RANGE_DAYS} days at a time")
    tiers = {t["key"] for t in screen.tiers}
    if set(body.prices) != tiers:
        raise _bad("prices", "Set a price for every tier of this screen")

    starts = [
        s for s in occurrences(body.days, body.times, body.from_date, body.to_date) if s > now
    ]
    if not starts:
        raise _bad("times", "None of these days and times are in the future")
    # Overlap within the batch itself (two start times closer than the runtime).
    for a, b in zip(starts, starts[1:], strict=False):
        if clashes(a, ends(a, film.runtime_min), b, ends(b, film.runtime_min)):
            local = b.astimezone(IST)
            raise ApiError(
                "overlap",
                f"{local:%H:%M} starts before the {a.astimezone(IST):%H:%M} show of "
                f"{film.title} ({planned_minutes(film.runtime_min)} min) ends and the screen "
                "is cleaned",
                status=409,
                details={"show": {"film_title": film.title, "starts_at": a.isoformat()}},
            )
    busy = await busy_on_screen(db, screen.id, body.from_date, body.to_date)
    for s in starts:
        e = ends(s, film.runtime_min)
        for other in busy:
            if clashes(s, e, other.starts_at, other.ends_at):
                when = other.starts_at.astimezone(IST)
                raise ApiError(
                    "overlap",
                    f"Clashes with {other.film_title} at {when:%H:%M} on {when:%a %d %b} "
                    f"in {screen.name}",
                    status=409,
                    details={
                        "show": {
                            "film_title": other.film_title,
                            "starts_at": other.starts_at.isoformat(),
                        }
                    },
                )

    schedule = ShowSchedule(
        screen_id=screen.id,
        film_id=film.id,
        language=body.language,
        format=body.format,
        days_of_week=sorted(set(body.days)),
        times=sorted(set(body.times)),
        from_date=body.from_date,
        to_date=body.to_date,
        prices=dict(body.prices),
        materialised_until=body.to_date,
    )
    db.add(schedule)
    await db.flush()
    created = await materialise_schedule(db, schedule, body.from_date, body.to_date, now=now)
    await db.commit()
    shows = await _shows(db, business, now, where=[Show.schedule_id == schedule.id], limit=6)
    return BulkResult(created=created, first=starts[0], last=starts[-1], shows=shows)


async def _shows(
    db: AsyncSession,
    business: Business,
    now: datetime,
    *,
    where: list,  # type: ignore[type-arg]
    limit: int | None = None,
) -> list[OwnerShow]:
    q = (
        select(Show, Film, Screen, Cinema)
        .join(Film, Film.id == Show.film_id)
        .join(Screen, Screen.id == Show.screen_id)
        .join(Cinema, Cinema.id == Screen.cinema_id)
        .where(Cinema.business_id == business.id, *where)
        .order_by(Show.starts_at, Cinema.name, Screen.name)
    )
    if limit:
        q = q.limit(limit)
    rows = [r._tuple() for r in (await db.execute(q)).all()]
    ids = [r[0].id for r in rows]
    sold: dict[uuid.UUID, int] = {}
    scanned: dict[uuid.UUID, int] = {}
    revenue: dict[uuid.UUID, int] = {}
    if ids:
        sold = _pairs(
            await db.execute(
                select(Ticket.show_id, func.count())
                .where(Ticket.show_id.in_(ids))
                .group_by(Ticket.show_id)
            )
        )
        scanned = _pairs(
            await db.execute(
                select(Ticket.show_id, func.count())
                .where(Ticket.show_id.in_(ids), Ticket.checked_in_at.is_not(None))
                .group_by(Ticket.show_id)
            )
        )
        revenue = _pairs(
            await db.execute(
                select(Order.show_id, func.sum(Order.subtotal_paise))
                .where(Order.show_id.in_(ids), Order.status == OrderStatus.PAID)
                .group_by(Order.show_id)
            )
        )
    public_business = business.status == BusinessStatus.VERIFIED
    return [
        OwnerShow(
            id=show.id,
            starts_at=show.starts_at,
            ends_at=show.ends_at,
            status=show.status.value,  # type: ignore[arg-type]
            film=ShowFilmRef(
                id=film.id,
                slug=film.slug,
                title=film.title,
                poster_url=film.poster_url,
                runtime_min=film.runtime_min,
            ),  # fmt: skip
            language=show.language,
            format=show.format,
            cinema_name=cinema.name,
            screen_id=screen.id,
            screen_name=screen.name,
            seat_count=screen.seat_count,
            sold=sold.get(show.id, 0),
            checked_in=scanned.get(show.id, 0),
            revenue_paise=int(revenue.get(show.id, 0) or 0),
            public=public_business and film.status == FilmStatus.NOW_SHOWING,
        )
        for show, film, screen, cinema in rows
    ]


def _day(day: date) -> tuple[datetime, datetime]:
    start = datetime.combine(day, datetime.min.time(), tzinfo=IST)
    return start, start + timedelta(days=1)


async def shows_on(
    db: AsyncSession, business: Business, day: date | None, now: datetime
) -> OwnerShows:
    today = ist_today(now)
    day = day or today
    lo, hi = _day(day)
    shows = await _shows(
        db, business, now,
        where=[Show.starts_at >= lo, Show.starts_at < hi, Show.status == ShowStatus.SCHEDULED],
    )  # fmt: skip
    strip_lo, _ = _day(today)
    strip_hi = strip_lo + timedelta(days=14)
    counts: dict[date, int] = defaultdict(int)
    for (starts,) in (
        await db.execute(
            select(Show.starts_at)
            .join(Screen, Screen.id == Show.screen_id)
            .join(Cinema, Cinema.id == Screen.cinema_id)
            .where(
                Cinema.business_id == business.id,
                Show.starts_at >= strip_lo,
                Show.starts_at < strip_hi,
                Show.status == ShowStatus.SCHEDULED,
            )
        )
    ).tuples():
        counts[starts.astimezone(IST).date()] += 1
    return OwnerShows(
        date=day,
        dates=[
            DayCount(date=today + timedelta(days=i), show_count=counts[today + timedelta(days=i)])
            for i in range(14)
        ],
        shows=shows,
    )


async def own_show(
    db: AsyncSession, business: Business, show_id: str | uuid.UUID, now: datetime
) -> OwnerShow:
    found = await _shows(db, business, now, where=[Show.id == parse_id(show_id)])
    if not found:
        raise ApiError("not_found", "No such show")
    return found[0]


async def bookings(db: AsyncSession, business: Business, show_id: str, now: datetime) -> Bookings:
    show = await own_show(db, business, show_id, now)
    screen = await db.get(Screen, show.screen_id)
    assert screen is not None
    labels = {t["key"]: t["label"] for t in screen.tiers}
    orders = (
        (
            await db.execute(
                select(Order, User)
                .join(User, User.id == Order.user_id)
                .where(Order.show_id == show.id, Order.status == OrderStatus.PAID)
                .order_by(Order.paid_at)
            )
        )
        .tuples()
        .all()
    )
    seat_rows = (
        (
            await db.execute(
                select(OrderSeat.order_id, Seat.row_label, Seat.number, OrderSeat.tier_key)
                .join(Seat, Seat.id == OrderSeat.seat_id)
                .where(OrderSeat.order_id.in_([o.id for o, _ in orders]))
                .order_by(Seat.row_label, Seat.number)
            )
        )
        .tuples()
        .all()
        if orders
        else []
    )
    seats: dict[uuid.UUID, list[str]] = defaultdict(list)
    tiers: dict[uuid.UUID, list[str]] = defaultdict(list)
    for oid, row, n, tier in seat_rows:
        seats[oid].append(seat_label(row, n))
        tiers[oid].append(labels.get(tier, tier))
    scanned = _pairs(
        await db.execute(
            select(Ticket.order_id, func.count())
            .where(Ticket.show_id == show.id, Ticket.checked_in_at.is_not(None))
            .group_by(Ticket.order_id)
        )
    )
    return Bookings(
        show=show,
        bookings=[
            Booking(
                order_id=o.id,
                name=u.name,
                email=u.email,
                seats=seats[o.id],
                tier_labels=list(dict.fromkeys(tiers[o.id])),
                amount_paise=o.total_paise,
                payment_method=o.payment_method,
                paid_at=o.paid_at,
                checked_in=scanned.get(o.id, 0),
            )
            for o, u in orders
        ],
    )


def csv_safe(value: object) -> object:
    """A cell a spreadsheet won't run: text starting with = + - @ (or a tab / CR) gets a quote."""
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@", chr(9), chr(13)):
        return "'" + value
    return value


def bookings_csv(data: Bookings) -> str:
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["booking_id", "name", "email", "seats", "tiers", "amount_inr", "payment",
                "paid_at_ist", "checked_in"])  # fmt: skip
    for b in data.bookings:
        w.writerow(
            [
                csv_safe(cell)
                for cell in (
                    str(b.order_id)[:8].upper(),
                    b.name,
                    b.email,
                    " ".join(b.seats),
                    " / ".join(b.tier_labels),
                    f"{b.amount_paise / 100:.2f}",
                    b.payment_method or "",
                    b.paid_at.astimezone(IST).strftime("%Y-%m-%d %H:%M") if b.paid_at else "",
                    b.checked_in,
                )
            ]
        )
    return out.getvalue()


# --- door (B10) -----------------------------------------------------------------------------------


async def check_in(
    db: AsyncSession,
    settings: Settings,
    business: Business,
    *,
    token: str,
    show_id: uuid.UUID,
    now: datetime,
) -> CheckInResult:
    """Verify the QR and mark the ticket used — once. `UPDATE … WHERE checked_in_at IS NULL`
    makes that atomic across any number of ushers' phones."""
    show = await own_show(db, business, show_id, now)

    async def counts() -> tuple[int, int]:
        sold = await db.scalar(
            select(func.count()).select_from(Ticket).where(Ticket.show_id == show.id)
        )
        admitted = await db.scalar(
            select(func.count())
            .select_from(Ticket)
            .where(Ticket.show_id == show.id, Ticket.checked_in_at.is_not(None))
        )
        return int(admitted or 0), int(sold or 0)

    verified = tokens.verify(settings, token.strip(), now=now)
    ticket = await db.get(Ticket, verified.ticket_id) if verified else None
    if verified is None or ticket is None or ticket.show_id != verified.show_id:
        admitted, sold = await counts()
        return CheckInResult(
            result="invalid", message="Not a Frontrow ticket", admitted=admitted, sold=sold
        )
    seat = await db.get(Seat, ticket.seat_id)
    owner = await db.get(User, ticket.user_id)
    label = seat_label(seat.row_label, seat.number) if seat else None
    name = owner.name if owner else None
    if ticket.show_id != show.id:
        other = await db.get(Show, ticket.show_id)
        film = await db.get(Film, other.film_id) if other else None
        when = other.starts_at.astimezone(IST).strftime("%a %d %b, %H:%M") if other else ""
        admitted, sold = await counts()
        return CheckInResult(
            result="wrong_show",
            message=f"Ticket for {film.title if film else 'another show'} · {when}".strip(" ·"),
            seat=label, name=name, admitted=admitted, sold=sold,
        )  # fmt: skip
    stamped = await db.scalar(
        update(Ticket)
        .where(Ticket.id == ticket.id, Ticket.checked_in_at.is_(None))
        .values(checked_in_at=now)
        .returning(Ticket.checked_in_at)
    )
    await db.commit()
    admitted, sold = await counts()
    if stamped is None:
        await db.refresh(ticket)
        at = ticket.checked_in_at
        used = f"Already checked in at {at.astimezone(IST):%H:%M}" if at else "Already checked in"
        return CheckInResult(
            result="used",
            message=used,
            seat=label, name=name, checked_in_at=at, admitted=admitted, sold=sold,
        )  # fmt: skip
    return CheckInResult(
        result="valid", message="Valid — let them in", seat=label, name=name,
        checked_in_at=stamped, admitted=admitted, sold=sold,
    )  # fmt: skip
