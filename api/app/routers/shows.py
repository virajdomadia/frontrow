"""Seat-map routes (06 §C): `/shows/{id}`, `/screens/{id}/layout`, `/shows/{id}/seats`, and the
hold engine's `POST/DELETE /shows/{id}/holds`.

A screen's layout never changes once generated, so it is cached for a year; the show detail is
catalogue-fresh (a minute, never past the start); seat state and holds are live and never
cached. Reads and hold writes answer 410 `show_closed` once the show has started or was
cancelled.
"""

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, Response
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.db import get_session
from app.redis import optional_redis, require_redis
from app.routers.catalog import cache_until
from app.schemas.layouts import Layout
from app.schemas.shows import HoldGranted, HoldRequest, SeatState, ShowDetail
from app.services import shows
from app.services.auth import Auth, client_ip, holder_of, optional_auth

router = APIRouter(tags=["seat map"])

IMMUTABLE = "public, max-age=31536000, s-maxage=31536000, immutable"

Db = Annotated[AsyncSession, Depends(get_session)]
OptAuth = Annotated[Auth | None, Depends(optional_auth)]


@router.get("/shows/{show_id}", response_model=ShowDetail)
async def get_show(
    show_id: str,
    response: Response,
    db: Db,
    redis: Annotated[Redis | None, Depends(optional_redis)],
) -> ShowDetail:
    now = datetime.now(UTC)
    detail = await shows.get_show(db, show_id, now=now, redis=redis)
    response.headers["Cache-Control"] = cache_until(detail.starts_at, now)
    return detail


@router.get("/screens/{screen_id}/layout", response_model=Layout)
async def get_layout(screen_id: str, response: Response, db: Db) -> Any:
    response.headers["Cache-Control"] = IMMUTABLE
    return await shows.get_layout(db, screen_id)


@router.get("/shows/{show_id}/seats", response_model=SeatState)
async def get_seats(
    show_id: str,
    request: Request,
    response: Response,
    db: Db,
    auth: OptAuth,
    redis: Annotated[Redis | None, Depends(optional_redis)],
) -> SeatState:
    response.headers["Cache-Control"] = "no-store"
    holder = holder_of(request, response, auth, create=False)
    return await shows.seat_state(db, show_id, redis=redis, holder=holder, now=datetime.now(UTC))


@router.post(
    "/shows/{show_id}/holds",
    response_model=HoldGranted,
    responses={409: {"description": "`seat_taken` — `details.taken` names the seats"}},
)
async def place_holds(
    show_id: str,
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
    return await shows.place_holds(
        db,
        redis,
        show_id,
        body.seat_ids,
        holder=holder,
        ip=client_ip(request, settings),
        ttl_seconds=settings.hold_ttl_seconds,
        per_minute=settings.holds_per_minute,
        now=datetime.now(UTC),
    )


@router.delete("/shows/{show_id}/holds", status_code=204)
async def drop_holds(
    show_id: str,
    body: HoldRequest,
    request: Request,
    response: Response,
    auth: OptAuth,
    redis: Annotated[Redis, Depends(require_redis)],
) -> None:
    holder = holder_of(request, response, auth, create=False)
    if holder is not None:
        await shows.drop_holds(redis, show_id, body.seat_ids, holder=holder)
