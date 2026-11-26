"""Public catalog routes (06 §C): `/events`, `/events/{slug}`, `/home`. Cached at the edge for
a minute (04 §9); the seat map routes (F1) are `no-store`."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.schemas.events import EventDetail, EventList, Home
from app.services import events

router = APIRouter(tags=["catalog"])

CACHE = "public, s-maxage=60, stale-while-revalidate=300"
RELATIVE_DATES = ("today", "tomorrow", "weekend")


def _cached(response: Response) -> None:
    response.headers["Cache-Control"] = CACHE


def cache_until(until: datetime, now: datetime) -> str:
    """`CACHE`, cut short so no shared cache serves the response — fresh or stale — past `until`:
    `?date=today` means another day after IST midnight, and a showtime is closed once it starts.
    """
    left = int((until - now).total_seconds())
    if left <= 0:
        return "no-store"
    fresh = min(60, left)
    return f"public, s-maxage={fresh}, stale-while-revalidate={min(300, left - fresh)}"


def next_ist_midnight(now: datetime) -> datetime:
    return events.day_start(now.astimezone(events.IST).date() + timedelta(days=1))


@router.get("/events", response_model=EventList)
async def list_events(
    response: Response,
    db: Annotated[AsyncSession, Depends(get_session)],
    date: Annotated[
        str | None,
        Query(
            pattern=r"^(today|tomorrow|weekend|\d{4}-\d{2}-\d{2})$",
            description="today · tomorrow · weekend · YYYY-MM-DD (IST days)",
        ),
    ] = None,
    type: Literal["movie", "concert"] | None = None,
    genre: Annotated[str | None, Query(max_length=40)] = None,
    venue: uuid.UUID | None = None,
    sort: Literal["soonest", "price", "title"] = "soonest",
) -> EventList:
    now = datetime.now(UTC)
    if date in RELATIVE_DATES:
        response.headers["Cache-Control"] = cache_until(next_ist_midnight(now), now)
    else:
        _cached(response)
    params = events.ListParams(date=date, type=type, genre=genre, venue=venue, sort=sort)
    return await events.list_events(db, params, now=now)


@router.get("/events/{slug}", response_model=EventDetail)
async def get_event(
    slug: str, response: Response, db: Annotated[AsyncSession, Depends(get_session)]
) -> EventDetail:
    _cached(response)
    return await events.get_event(db, slug, now=datetime.now(UTC))


@router.get("/home", response_model=Home)
async def home(response: Response, db: Annotated[AsyncSession, Depends(get_session)]) -> Home:
    _cached(response)
    return await events.home(db, now=datetime.now(UTC))
