"""Seat-map reads (06 §C): showtime detail, the venue layout, and the live seat state.

Sold seats come from `tickets` (Postgres is the truth for a sale). Holds live in Redis from F2
on; until then `live_holds()` is the one seam that returns nothing, so the route, the contract
and the web map are already shaped for them.

A showtime that has started or was cancelled is closed: both reads answer 410
`showtime_closed` (the same rule as the web's book-page guard), with enough in `details` for
the web to say so and link back to the event.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import ApiError
from app.models import Event, PriceTier, Showtime, Ticket, Venue
from app.models.enums import EventStatus, ShowtimeStatus
from app.schemas.events import TierPrice
from app.schemas.showtimes import (
    HeldSeat,
    SeatState,
    ShowtimeDetail,
    ShowtimeEvent,
    ShowtimeVenue,
)
from app.services.events import FILLING_AT

FEE_PAISE = 3000  # flat ₹30 per ticket (03 R5); F5's order total uses the same constant


@dataclass
class Holds:
    """Live holds for one showtime: `others` = someone else's, `mine` = the caller's."""

    v: int = 0
    others: list[HeldSeat] = field(default_factory=list)
    mine: list[str] = field(default_factory=list)


async def live_holds(showtime_id: uuid.UUID, sid: str | None) -> Holds:
    """F2 replaces this with the `holds:{st}` hash + `st:{st}:v` read (06 §B)."""
    return Holds()


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


async def get_showtime(db: AsyncSession, showtime_id: str, *, now: datetime) -> ShowtimeDetail:
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
    fill = (
        "sold_out"
        if sold >= venue.seat_count
        else "filling"
        if sold >= venue.seat_count * FILLING_AT
        else "available"
    )
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
        seats_left=venue.seat_count - sold,
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


async def seat_state(
    db: AsyncSession, showtime_id: str, *, sid: str | None, now: datetime
) -> SeatState:
    showtime, _, _ = await _load(db, showtime_id, now)
    st_id = showtime.id
    sold = [
        str(s) for s in await db.scalars(select(Ticket.seat_id).where(Ticket.showtime_id == st_id))
    ]
    holds = await live_holds(st_id, sid)
    return SeatState(v=holds.v, server_time=now, sold=sold, held=holds.others, mine=holds.mine)
