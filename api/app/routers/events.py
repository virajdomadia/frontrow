"""Public catalog routes (06 §C): `/events`, `/events/{slug}`, `/home`. Cached at the edge for
a minute (04 §9); the seat map routes (F1) are `no-store`."""

import uuid
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.schemas.events import EventDetail, EventList, Home
from app.services import events

router = APIRouter(tags=["catalog"])

CACHE = "public, s-maxage=60, stale-while-revalidate=300"


def _cached(response: Response) -> None:
    response.headers["Cache-Control"] = CACHE


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
    _cached(response)
    params = events.ListParams(date=date, type=type, genre=genre, venue=venue, sort=sort)
    return await events.list_events(db, params, now=datetime.now(UTC))


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
