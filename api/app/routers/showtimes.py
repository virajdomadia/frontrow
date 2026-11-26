"""Seat-map routes (06 §C): `/showtimes/{id}`, `/venues/{id}/layout`, `/showtimes/{id}/seats`,
and the hold engine's `POST/DELETE /showtimes/{id}/holds`.

The layout never changes once a venue is generated, so it is cached for a year; the detail is
catalog-fresh (a minute, never past the start); the seat state and holds are live and never
cached. Showtime reads and hold writes answer 410 `showtime_closed` once the show has started or
was cancelled.
"""

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, Response
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.db import get_session
from app.redis import optional_redis, require_redis
from app.routers.events import cache_until
from app.schemas.layouts import Layout
from app.schemas.showtimes import HoldGranted, HoldRequest, SeatState, ShowtimeDetail
from app.services import showtimes
from app.services.auth import Auth, holder_of, optional_auth

router = APIRouter(tags=["seat map"])

IMMUTABLE = "public, max-age=31536000, s-maxage=31536000, immutable"

Db = Annotated[AsyncSession, Depends(get_session)]
OptAuth = Annotated[Auth | None, Depends(optional_auth)]


@router.get("/showtimes/{showtime_id}", response_model=ShowtimeDetail)
async def get_showtime(
    showtime_id: str,
    response: Response,
    db: Db,
    redis: Annotated[Redis | None, Depends(optional_redis)],
) -> ShowtimeDetail:
    now = datetime.now(UTC)
    detail = await showtimes.get_showtime(db, showtime_id, now=now, redis=redis)
    # Fresh for a minute as the catalog is, but no cache may hand it out once the show starts.
    response.headers["Cache-Control"] = cache_until(detail.starts_at, now)
    return detail


@router.get("/venues/{venue_id}/layout", response_model=Layout)
async def get_layout(venue_id: str, response: Response, db: Db) -> Any:
    response.headers["Cache-Control"] = IMMUTABLE
    return await showtimes.get_layout(db, venue_id)


@router.get("/showtimes/{showtime_id}/seats", response_model=SeatState)
async def get_seats(
    showtime_id: str,
    request: Request,
    response: Response,
    db: Db,
    auth: OptAuth,
    redis: Annotated[Redis | None, Depends(optional_redis)],
) -> SeatState:
    response.headers["Cache-Control"] = "no-store"
    holder = holder_of(request, response, auth, create=False)
    return await showtimes.seat_state(
        db, showtime_id, redis=redis, holder=holder, now=datetime.now(UTC)
    )


@router.post(
    "/showtimes/{showtime_id}/holds",
    response_model=HoldGranted,
    responses={409: {"description": "`seat_taken` — `details.taken` names the seats"}},
)
async def place_holds(
    showtime_id: str,
    body: HoldRequest,
    request: Request,
    response: Response,
    db: Db,
    auth: OptAuth,
    redis: Annotated[Redis, Depends(require_redis)],
) -> HoldGranted:
    """Hold the caller's whole selection for 10 minutes — all of it or none of it."""
    settings: Settings = request.app.state.settings
    response.headers["Cache-Control"] = "no-store"
    holder = holder_of(request, response, auth, create=True)
    assert holder is not None
    return await showtimes.place_holds(
        db,
        redis,
        showtime_id,
        body.seat_ids,
        holder=holder,
        ttl_seconds=settings.hold_ttl_seconds,
        per_minute=settings.holds_per_minute,
        now=datetime.now(UTC),
    )


@router.delete("/showtimes/{showtime_id}/holds", status_code=204)
async def drop_holds(
    showtime_id: str,
    body: HoldRequest,
    request: Request,
    response: Response,
    db: Db,
    auth: OptAuth,
    redis: Annotated[Redis, Depends(require_redis)],
) -> None:
    holder = holder_of(request, response, auth, create=False)
    if holder is not None:
        await showtimes.drop_holds(db, redis, showtime_id, body.seat_ids, holder=holder)
