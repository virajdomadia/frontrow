"""Seat-map reads and hold writes (06 §C): showtime detail, the venue layout, the live seat
state, and `POST/DELETE /showtimes/{id}/holds`.

Sold seats come from `tickets` (Postgres is the truth for a sale); holds come from Redis
(`services/holds.py`). A hold request is checked against Postgres first — a sold seat is a 409
too — then taken all-or-none by one Lua script.

A showtime that has started or was cancelled is closed: every read and write answers 410
`showtime_closed` (the same rule as the web's book-page guard), with enough in `details` for
the web to say so and link back to the event.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import ApiError
from app.models import Event, PriceTier, Seat, Showtime, Ticket, Venue
from app.models.enums import EventStatus, ShowtimeStatus
from app.schemas.events import TierPrice
from app.schemas.showtimes import (
    HoldGranted,
    SeatState,
    ShowtimeDetail,
    ShowtimeEvent,
    ShowtimeVenue,
)
from app.services import holds
from app.services.events import fill_of

FEE_PAISE = 3000  # flat ₹30 per ticket (03 R5); the order total uses the same constant


def _bad_id(raw: str) -> uuid.UUID:
    try:
        return uuid.UUID(raw)
    except ValueError as e:
        raise ApiError("not_found", "No such showtime") from e


def _check_open(showtime: Showtime, event: Event, venue: Venue, now: datetime) -> None:
    cancelled = showtime.status == ShowtimeStatus.CANCELLED
    if not cancelled and showtime.starts_at > now:
        return
    raise ApiError(
        "showtime_closed",
        "This showtime was cancelled" if cancelled else "This show has already started",
        status=410,
        details={
            "reason": "cancelled" if cancelled else "started",
            "starts_at": showtime.starts_at.isoformat(),
            "event_slug": event.slug,
            "event_title": event.title,
            "venue_name": venue.name,
        },
    )


async def _load(db: AsyncSession, showtime_id: str, now: datetime) -> tuple[Showtime, Event, Venue]:
    row = (
        await db.execute(
            select(Showtime, Event, Venue)
            .join(Event, Event.id == Showtime.event_id)
            .join(Venue, Venue.id == Showtime.venue_id)
            .where(Showtime.id == _bad_id(showtime_id), Event.status == EventStatus.LIVE)
        )
    ).one_or_none()
    if row is None:
        raise ApiError("not_found", "No such showtime")
    showtime, event, venue = row._tuple()
    _check_open(showtime, event, venue, now)
    return showtime, event, venue


async def get_showtime(
    db: AsyncSession, showtime_id: str, *, now: datetime, redis: Redis | None = None
) -> ShowtimeDetail:
    showtime, event, venue = await _load(db, showtime_id, now)

    prices = {
        t.tier_key: t
        for t in await db.scalars(select(PriceTier).where(PriceTier.showtime_id == showtime.id))
    }
    # The legend's order (front to back) with this show's prices; a tier without a price is
    # not on sale, so it is left out and its seats render unavailable.
    tiers = [
        TierPrice(
            tier_key=t["key"],
            label=prices[t["key"]].label,
            price_paise=prices[t["key"]].price_paise,
        )
        for t in venue.layout["tiers"]
        if t["key"] in prices
    ]
    sold = (
        await db.scalar(
            select(func.count()).select_from(Ticket).where(Ticket.showtime_id == showtime.id)
        )
        or 0
    )
    held = (await holds.held_counts(redis, [showtime.id])).get(showtime.id, 0)
    fill = fill_of(venue.seat_count, sold, held)
    return ShowtimeDetail(
        id=showtime.id,
        starts_at=showtime.starts_at,
        status=showtime.status.value,  # type: ignore[arg-type]
        event=ShowtimeEvent(
            id=event.id,
            slug=event.slug,
            title=event.title,
            type=event.type.value,  # type: ignore[arg-type]
            genre=event.genre,
            rating=event.rating,
            duration_min=event.duration_min,
            poster_url=event.poster_url,
        ),
        venue=ShowtimeVenue(
            id=venue.id,
            name=venue.name,
            address=venue.address,
            seat_count=venue.seat_count,
            photo_url=venue.photo_url,
            template=venue.template.value,  # type: ignore[arg-type]
        ),
        tiers=tiers,
        layout_url=f"/venues/{venue.id}/layout",
        fee_paise=FEE_PAISE,
        fill=fill,  # type: ignore[arg-type]
        seats_left=max(venue.seat_count - sold - held, 0),
    )


async def get_layout(db: AsyncSession, venue_id: str) -> dict[str, Any]:
    try:
        vid = uuid.UUID(venue_id)
    except ValueError as e:
        raise ApiError("not_found", "No such venue") from e
    layout = await db.scalar(select(Venue.layout).where(Venue.id == vid))
    if layout is None:
        raise ApiError("not_found", "No such venue")
    return layout


async def _sold(db: AsyncSession, showtime_id: uuid.UUID) -> list[str]:
    return [
        str(s)
        for s in await db.scalars(select(Ticket.seat_id).where(Ticket.showtime_id == showtime_id))
    ]


async def seat_state(
    db: AsyncSession,
    showtime_id: str,
    *,
    redis: Redis | None,
    holder: str | None,
    now: datetime,
) -> SeatState:
    showtime, _, _ = await _load(db, showtime_id, now)
    sold = await _sold(db, showtime.id)
    live = await holds.snapshot(redis, showtime.id, holder, now=now)
    sold_set = set(sold)
    return SeatState(
        v=live.v,
        server_time=now,
        sold=sold,
        held=[h for h in live.others if h.seat_id not in sold_set],  # sold beats held
        mine=[m for m in live.mine if m not in sold_set],
        mine_expires_at=live.mine_expires_at,
    )


async def _check_seats(
    db: AsyncSession, showtime: Showtime, venue: Venue, seat_ids: list[str]
) -> list[str]:
    """Every id is a seat of this venue in a tier this show sells; duplicates dropped."""
    ids: list[str] = []
    for raw in dict.fromkeys(seat_ids):
        try:
            ids.append(str(uuid.UUID(raw)))
        except ValueError as e:
            raise ApiError(
                "validation", "Unknown seat", details={"fields": {"seat_ids": raw}}
            ) from e
    on_sale = select(PriceTier.tier_key).where(PriceTier.showtime_id == showtime.id)
    found = {
        str(s)
        for s in await db.scalars(
            select(Seat.id).where(
                Seat.venue_id == venue.id,
                Seat.id.in_([uuid.UUID(i) for i in ids]),
                Seat.tier_key.in_(on_sale),
            )
        )
    }
    missing = [i for i in ids if i not in found]
    if missing:
        raise ApiError(
            "validation",
            "Some seats aren't on sale for this show",
            details={"fields": {"seat_ids": "not on sale"}, "seats": missing},
        )
    return ids


async def place_holds(
    db: AsyncSession,
    redis: Redis,
    showtime_id: str,
    seat_ids: list[str],
    *,
    holder: str,
    ttl_seconds: int,
    per_minute: int,
    now: datetime,
) -> HoldGranted:
    """Hold the whole selection or nothing (R4). Sold seats → 409 like held ones."""
    showtime, _, venue = await _load(db, showtime_id, now)
    if len(set(seat_ids)) > holds.MAX_SEATS:
        raise ApiError(
            "too_many_seats",
            f"Up to {holds.MAX_SEATS} seats per booking",
            status=422,
            details={"max": holds.MAX_SEATS},
        )
    ids = await _check_seats(db, showtime, venue, seat_ids)
    await holds.rate_limit(redis, holder, per_minute)

    sold = set(await _sold(db, showtime.id)) & set(ids)
    if sold:
        raise ApiError(
            "seat_taken",
            "That seat was just sold" if len(sold) == 1 else "Those seats were just sold",
            status=409,
            details={"taken": sorted(sold)},
        )
    # The cap counts seats held from another tab of the same holder too.
    live = await holds.snapshot(redis, showtime.id, holder, now=now)
    if len(set(live.mine) | set(ids)) > holds.MAX_SEATS:
        raise ApiError(
            "too_many_seats",
            f"Up to {holds.MAX_SEATS} seats per booking",
            status=422,
            details={"max": holds.MAX_SEATS},
        )
    granted = await holds.acquire(redis, showtime.id, holder, ids, ttl_seconds=ttl_seconds, now=now)
    return HoldGranted(expires_at=granted.expires_at, held=granted.held)


async def drop_holds(
    db: AsyncSession, redis: Redis, showtime_id: str, seat_ids: list[str], *, holder: str
) -> int:
    """Release the holder's own holds on these seats. Works on a closed showtime too, so a
    stale tab can always let go."""
    try:
        st = uuid.UUID(showtime_id)
    except ValueError as e:
        raise ApiError("not_found", "No such showtime") from e
    ids = []
    for raw in dict.fromkeys(seat_ids):
        try:
            ids.append(str(uuid.UUID(raw)))
        except ValueError:
            continue
    return await holds.release(redis, st, holder, ids)
