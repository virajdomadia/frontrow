"""Seat-map routes (06 §C): `/showtimes/{id}`, `/venues/{id}/layout`, `/showtimes/{id}/seats`.

The layout never changes once a venue is generated, so it is cached for a year; the detail is
catalog-fresh (a minute); the seat state is live and never cached.
"""

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Cookie, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.routers.events import CACHE
from app.schemas.layouts import Layout
from app.schemas.showtimes import SeatState, ShowtimeDetail
from app.services import showtimes

router = APIRouter(tags=["seat map"])

IMMUTABLE = "public, max-age=31536000, s-maxage=31536000, immutable"


@router.get("/showtimes/{showtime_id}", response_model=ShowtimeDetail)
async def get_showtime(
    showtime_id: str, response: Response, db: Annotated[AsyncSession, Depends(get_session)]
) -> ShowtimeDetail:
    response.headers["Cache-Control"] = CACHE
    return await showtimes.get_showtime(db, showtime_id)


@router.get("/venues/{venue_id}/layout", response_model=Layout)
async def get_layout(
    venue_id: str, response: Response, db: Annotated[AsyncSession, Depends(get_session)]
) -> Any:
    response.headers["Cache-Control"] = IMMUTABLE
    return await showtimes.get_layout(db, venue_id)


@router.get("/showtimes/{showtime_id}/seats", response_model=SeatState)
async def get_seats(
    showtime_id: str,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_session)],
    fr_sid: Annotated[str | None, Cookie()] = None,
) -> SeatState:
    response.headers["Cache-Control"] = "no-store"
    return await showtimes.seat_state(db, showtime_id, sid=fr_sid, now=datetime.now(UTC))
