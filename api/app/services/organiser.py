"""Organiser console (R8): venues from templates, events, showtimes with tier prices, bookings.

Every read and write is scoped to the signed-in organiser: another organiser's venue, event or
showtime simply doesn't exist (404), so ids can't be probed. A showtime with tickets sold can't
be cancelled or moved in v1 (409 `has_sales`) — refunds UI is out of scope.
"""

from __future__ import annotations

import csv
import io
import re
import unicodedata
import uuid
from collections import defaultdict
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import ApiError
from app.models import Event, Order, OrderSeat, PriceTier, Seat, Showtime, Ticket, User, Venue
from app.models.enums import EventStatus, EventType, OrderStatus, ShowtimeStatus
from app.schemas.events import TierPrice
from app.schemas.layouts import LayoutTier
from app.schemas.organiser import (
    Booking,
    Bookings,
    CreateShowtime,
    CreateVenue,
    EventFields,
    EventPatch,
    OrganiserEvent,
    OrganiserShowtime,
    OrganiserVenue,
    OrganiserVenueDetail,
    ShowtimeEventRef,
    ShowtimePatch,
    ShowtimeVenueRef,
)
from app.services.orders import seat_label
from app.services.venues import create_venue


def _pairs(result: Any) -> dict[Any, Any]:
    """`{key: value}` from a two-column result. (`dict(result)` would treat the result as a
    mapping — it has `.keys()` — and fail.)"""
    return {k: v for k, v in result.tuples()}


def _uuid(raw: str | uuid.UUID, what: str) -> uuid.UUID:
    if isinstance(raw, uuid.UUID):
        return raw
    try:
        return uuid.UUID(raw)
    except ValueError as e:
        raise ApiError("not_found", f"No such {what}") from e


# --- venues ---------------------------------------------------------------------------------------


async def _upcoming_by_venue(db: AsyncSession, now: datetime) -> dict[uuid.UUID, int]:
    rows = await db.execute(
        select(Showtime.venue_id, func.count())
        .where(Showtime.starts_at > now, Showtime.status == ShowtimeStatus.SCHEDULED)
        .group_by(Showtime.venue_id)
    )
    return {vid: n for vid, n in rows.tuples()}


def _venue_out(v: Venue, upcoming: int) -> OrganiserVenue:
    return OrganiserVenue(
        id=v.id,
        name=v.name,
        address=v.address,
        photo_url=v.photo_url,
        template=v.template.value,  # type: ignore[arg-type]
        seat_count=v.seat_count,
        tiers=[LayoutTier(**t) for t in v.layout["tiers"]],
        upcoming_showtimes=upcoming,
        created_at=v.created_at,
    )


async def list_venues(db: AsyncSession, organiser: User, now: datetime) -> list[OrganiserVenue]:
    venues = await db.scalars(
        select(Venue).where(Venue.organiser_id == organiser.id).order_by(Venue.created_at)
    )
    upcoming = await _upcoming_by_venue(db, now)
    return [_venue_out(v, upcoming.get(v.id, 0)) for v in venues]


async def own_venue(db: AsyncSession, organiser: User, venue_id: str | uuid.UUID) -> Venue:
    venue = await db.get(Venue, _uuid(venue_id, "venue"))
    if venue is None or venue.organiser_id != organiser.id:
        raise ApiError("not_found", "No such venue")
    return venue


async def venue_detail(
    db: AsyncSession, organiser: User, venue_id: str, now: datetime
) -> OrganiserVenueDetail:
    v = await own_venue(db, organiser, venue_id)
    base = _venue_out(v, (await _upcoming_by_venue(db, now)).get(v.id, 0))
    return OrganiserVenueDetail(**base.model_dump(), knobs=v.knobs, layout=v.layout)  # type: ignore[arg-type]


async def add_venue(
    db: AsyncSession, organiser: User, body: CreateVenue, now: datetime
) -> OrganiserVenue:
    name = body.name.strip()
    clash = await db.scalar(
        select(Venue.id).where(Venue.organiser_id == organiser.id, Venue.name == name)
    )
    if clash:
        raise ApiError(
            "conflict",
            "You already have a venue with this name",
            details={"fields": {"name": "taken"}},
        )
    venue = await create_venue(
        db, organiser.id, name=name, address=body.address.strip(), photo_url=body.photo_url,
        knobs=body.knobs,
    )  # fmt: skip
    await db.commit()
    return _venue_out(venue, 0)


# --- events ---------------------------------------------------------------------------------------


def slugify(title: str) -> str:
    text = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60] or "event"


async def _unique_slug(db: AsyncSession, title: str, *, keep: uuid.UUID | None = None) -> str:
    base = slugify(title)
    taken = {
        s
        for s in await db.scalars(
            select(Event.slug).where(Event.slug.like(f"{base}%"), Event.id != keep)
            if keep
            else select(Event.slug).where(Event.slug.like(f"{base}%"))
        )
    }
    if base not in taken:
        return base
    n = 2
    while f"{base}-{n}" in taken:
        n += 1
    return f"{base}-{n}"


async def _event_stats(
    db: AsyncSession, event_ids: list[uuid.UUID], now: datetime
) -> tuple[dict[uuid.UUID, int], dict[uuid.UUID, int]]:
    if not event_ids:
        return {}, {}
    upcoming = _pairs(
        await db.execute(
            select(Showtime.event_id, func.count())
            .where(
                Showtime.event_id.in_(event_ids),
                Showtime.starts_at > now,
                Showtime.status == ShowtimeStatus.SCHEDULED,
            )
            .group_by(Showtime.event_id)
        )
    )
    sold = _pairs(
        await db.execute(
            select(Showtime.event_id, func.count(Ticket.id))
            .join(Ticket, Ticket.showtime_id == Showtime.id)
            .where(Showtime.event_id.in_(event_ids))
            .group_by(Showtime.event_id)
        )
    )
    return upcoming, sold


def _event_out(e: Event, upcoming: int, sold: int) -> OrganiserEvent:
    return OrganiserEvent(
        id=e.id,
        slug=e.slug,
        title=e.title,
        type=e.type.value,  # type: ignore[arg-type]
        genre=e.genre,
        duration_min=e.duration_min,
        rating=e.rating,
        synopsis=e.synopsis,
        cast_lineup=list(e.cast_lineup),
        poster_url=e.poster_url,
        gallery_urls=list(e.gallery_urls),
        status=e.status.value,  # type: ignore[arg-type]
        upcoming_showtimes=upcoming,
        tickets_sold=sold,
        created_at=e.created_at,
    )


async def list_events(db: AsyncSession, organiser: User, now: datetime) -> list[OrganiserEvent]:
    events = list(
        await db.scalars(
            select(Event).where(Event.organiser_id == organiser.id).order_by(Event.title)
        )
    )
    upcoming, sold = await _event_stats(db, [e.id for e in events], now)
    return [_event_out(e, upcoming.get(e.id, 0), sold.get(e.id, 0)) for e in events]


async def own_event(db: AsyncSession, organiser: User, event_id: str | uuid.UUID) -> Event:
    event = await db.get(Event, _uuid(event_id, "event"))
    if event is None or event.organiser_id != organiser.id:
        raise ApiError("not_found", "No such event")
    return event


async def event_detail(
    db: AsyncSession, organiser: User, event_id: str, now: datetime
) -> OrganiserEvent:
    e = await own_event(db, organiser, event_id)
    upcoming, sold = await _event_stats(db, [e.id], now)
    return _event_out(e, upcoming.get(e.id, 0), sold.get(e.id, 0))


def _apply(event: Event, fields: dict[str, Any]) -> None:
    for key, value in fields.items():
        if key == "type":
            value = EventType(value)
        elif key == "status":
            value = EventStatus(value)
        elif key in ("title", "genre", "synopsis") and isinstance(value, str):
            value = value.strip()
        elif key == "rating" and isinstance(value, str):
            value = value.strip() or None
        setattr(event, key, value)


async def add_event(
    db: AsyncSession, organiser: User, body: EventFields, now: datetime
) -> OrganiserEvent:
    event = Event(organiser_id=organiser.id, slug=await _unique_slug(db, body.title))
    _apply(event, body.model_dump())
    db.add(event)
    await db.commit()
    return _event_out(event, 0, 0)


async def edit_event(
    db: AsyncSession, organiser: User, event_id: str, body: EventPatch, now: datetime
) -> OrganiserEvent:
    """The slug stays put once created, so shared links keep working."""
    event = await own_event(db, organiser, event_id)
    _apply(event, body.model_dump(exclude_unset=True))
    await db.commit()
    return await event_detail(db, organiser, event_id, now)


# --- showtimes ------------------------------------------------------------------------------------


async def _showtime_rows(
    db: AsyncSession, organiser: User, *, showtime_id: uuid.UUID | None = None,
    event_id: uuid.UUID | None = None,
) -> list[OrganiserShowtime]:  # fmt: skip
    q = (
        select(Showtime, Event, Venue)
        .join(Event, Event.id == Showtime.event_id)
        .join(Venue, Venue.id == Showtime.venue_id)
        .where(Event.organiser_id == organiser.id)
        .order_by(Showtime.starts_at)
    )
    if showtime_id is not None:
        q = q.where(Showtime.id == showtime_id)
    if event_id is not None:
        q = q.where(Showtime.event_id == event_id)
    rows = [r._tuple() for r in (await db.execute(q)).all()]
    ids = [s.id for s, _, _ in rows]
    if not ids:
        return []
    tiers: dict[uuid.UUID, list[PriceTier]] = defaultdict(list)
    for t in await db.scalars(select(PriceTier).where(PriceTier.showtime_id.in_(ids))):
        tiers[t.showtime_id].append(t)
    sold = _pairs(
        await db.execute(
            select(Ticket.showtime_id, func.count())
            .where(Ticket.showtime_id.in_(ids))
            .group_by(Ticket.showtime_id)
        )
    )
    revenue = _pairs(
        await db.execute(
            select(Order.showtime_id, func.coalesce(func.sum(Order.subtotal_paise), 0))
            .where(Order.showtime_id.in_(ids), Order.status == OrderStatus.PAID)
            .group_by(Order.showtime_id)
        )
    )
    out = []
    for s, e, v in rows:
        order = [t["key"] for t in v.layout["tiers"]]
        st_tiers = sorted(
            tiers[s.id], key=lambda t: order.index(t.tier_key) if t.tier_key in order else 99
        )
        out.append(
            OrganiserShowtime(
                id=s.id,
                starts_at=s.starts_at,
                status=s.status.value,  # type: ignore[arg-type]
                event=ShowtimeEventRef(
                    id=e.id,
                    slug=e.slug,
                    title=e.title,
                    type=e.type.value,  # type: ignore[arg-type]
                    status=e.status.value,  # type: ignore[arg-type]
                ),  # fmt: skip
                venue=ShowtimeVenueRef(id=v.id, name=v.name, template=v.template.value),  # type: ignore[arg-type]
                tiers=[
                    TierPrice(tier_key=t.tier_key, label=t.label, price_paise=t.price_paise)
                    for t in st_tiers
                ],
                seat_count=v.seat_count,
                sold=sold.get(s.id, 0),
                revenue_paise=int(revenue.get(s.id, 0)),
            )
        )
    return out


async def list_showtimes(
    db: AsyncSession, organiser: User, *, event_id: str | None
) -> list[OrganiserShowtime]:
    return await _showtime_rows(
        db, organiser, event_id=_uuid(event_id, "event") if event_id else None
    )


async def showtime_detail(db: AsyncSession, organiser: User, showtime_id: str) -> OrganiserShowtime:
    rows = await _showtime_rows(db, organiser, showtime_id=_uuid(showtime_id, "showtime"))
    if not rows:
        raise ApiError("not_found", "No such showtime")
    return rows[0]


def _field_error(field: str, message: str) -> ApiError:
    return ApiError("validation", message, details={"fields": {field: message}})


async def add_showtime(
    db: AsyncSession, organiser: User, body: CreateShowtime, now: datetime
) -> OrganiserShowtime:
    event = await own_event(db, organiser, body.event_id)
    venue = await own_venue(db, organiser, body.venue_id)
    if body.starts_at.tzinfo is None:
        raise _field_error("starts_at", "Include a timezone")
    if body.starts_at <= now:
        raise _field_error("starts_at", "Pick a time in the future")
    layout_tiers = {t["key"]: t["label"] for t in venue.layout["tiers"]}
    seen: set[str] = set()
    for t in body.tiers:
        if t.tier_key not in layout_tiers:
            raise _field_error("tiers", f"{venue.name} has no tier '{t.tier_key}'")
        if t.tier_key in seen:
            raise _field_error("tiers", f"Tier '{t.tier_key}' is priced twice")
        seen.add(t.tier_key)
    showtime = Showtime(
        event_id=event.id,
        venue_id=venue.id,
        starts_at=body.starts_at,
        status=ShowtimeStatus.SCHEDULED,
    )
    db.add(showtime)
    await db.flush()
    db.add_all(
        PriceTier(
            showtime_id=showtime.id,
            tier_key=t.tier_key,
            label=(t.label or "").strip() or layout_tiers[t.tier_key],
            price_paise=t.price_paise,
        )
        for t in body.tiers
    )
    await db.commit()
    return await showtime_detail(db, organiser, str(showtime.id))


async def edit_showtime(
    db: AsyncSession, organiser: User, showtime_id: str, body: ShowtimePatch, now: datetime
) -> OrganiserShowtime:
    current = await showtime_detail(db, organiser, showtime_id)
    showtime = await db.get(Showtime, current.id)
    assert showtime is not None
    changes = body.model_dump(exclude_unset=True)
    if current.sold and (
        changes.get("status") == "cancelled"
        or ("starts_at" in changes and changes["starts_at"] != showtime.starts_at)
    ):
        raise ApiError(
            "has_sales",
            f"{current.sold} tickets are sold for this showtime, so it can't be cancelled or "
            "moved. Refunds arrive in a later version.",
            status=409,
            details={"sold": current.sold},
        )
    if "starts_at" in changes and changes["starts_at"] is not None:
        if changes["starts_at"] <= now:
            raise _field_error("starts_at", "Pick a time in the future")
        showtime.starts_at = changes["starts_at"]
    if changes.get("status"):
        showtime.status = ShowtimeStatus(changes["status"])
    await db.commit()
    return await showtime_detail(db, organiser, showtime_id)


# --- bookings -------------------------------------------------------------------------------------


async def bookings(db: AsyncSession, organiser: User, showtime_id: str) -> Bookings:
    showtime = await showtime_detail(db, organiser, showtime_id)
    venue = await db.get(Venue, showtime.venue.id)
    assert venue is not None
    sections = {s["key"]: s["label"] for s in venue.layout["sections"]}
    tier_names = {t.tier_key: t.label for t in showtime.tiers}
    orders = (
        await db.execute(
            select(Order, User)
            .join(User, User.id == Order.user_id)
            .where(Order.showtime_id == showtime.id, Order.status == OrderStatus.PAID)
            .order_by(Order.paid_at.desc(), Order.created_at.desc())
        )
    ).all()
    seats: dict[uuid.UUID, list[tuple[Seat, OrderSeat]]] = defaultdict(list)
    order_ids = [o.id for o, _ in (r._tuple() for r in orders)]
    if order_ids:
        for os_, seat in (
            await db.execute(
                select(OrderSeat, Seat)
                .join(Seat, Seat.id == OrderSeat.seat_id)
                .where(OrderSeat.order_id.in_(order_ids))
                .order_by(Seat.y, Seat.x)
            )
        ).tuples():
            seats[os_.order_id].append((seat, os_))
    out = []
    for order, user in (r._tuple() for r in orders):
        mine = seats[order.id]
        out.append(
            Booking(
                order_id=order.id,
                customer_name=user.name,
                customer_email=user.email,
                seats=[
                    seat_label(
                        venue.template.value,
                        sections.get(s.section_key, ""),
                        s.row_label,
                        s.number,
                    )  # fmt: skip
                    for s, _ in mine
                ],
                tier_labels=list(
                    dict.fromkeys(tier_names.get(o.tier_key, o.tier_key) for _, o in mine)
                ),
                tickets=len(mine),
                subtotal_paise=order.subtotal_paise,
                total_paise=order.total_paise,
                paid_at=order.paid_at,
            )
        )
    return Bookings(
        showtime=showtime,
        bookings=out,
        tickets=sum(b.tickets for b in out),
        revenue_paise=sum(b.subtotal_paise for b in out),
    )


CSV_COLUMNS = [
    "order_id", "paid_at", "customer", "email", "seats", "tiers", "tickets", "ticket_inr",
    "total_inr",
]  # fmt: skip


def bookings_csv(data: Bookings) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(CSV_COLUMNS)
    for b in data.bookings:
        writer.writerow(
            [
                b.order_id,
                b.paid_at.isoformat() if b.paid_at else "",
                _csv_safe(b.customer_name),
                _csv_safe(b.customer_email),
                " ".join(b.seats),
                " / ".join(b.tier_labels),
                b.tickets,
                f"{b.subtotal_paise / 100:.2f}",
                f"{b.total_paise / 100:.2f}",
            ]
        )
    return buf.getvalue()


def _csv_safe(value: str) -> str:
    """Spreadsheet formula injection: a cell starting with = + - @ is shown as text."""
    return f"'{value}" if value[:1] in ("=", "+", "-", "@", "\t", "\r") else value
