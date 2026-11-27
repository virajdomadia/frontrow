"""Seat-map routes (06 §C): `/shows/{id}`, `/screens/{id}/layout`, `/shows/{id}/seats`, and the
hold engine's `POST/DELETE /shows/{id}/holds`.

A screen's layout never changes once generated, so it is cached for a year; the show detail is
catalogue-fresh (a minute, never past the start); seat state and holds are live and never
cached. `/shows/{id}/stream` pushes the seat state on every change (L1); `/seats` stays as the
polling fallback. Reads and hold writes answer 410 `show_closed` once the show has started or was
cancelled.
"""

import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import StreamingResponse
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.db import get_session, side_session
from app.errors import ApiError
from app.redis import optional_redis, require_redis
from app.routers.catalog import cache_until
from app.schemas.layouts import Layout
from app.schemas.shows import HoldGranted, HoldRequest, SeatState, ShowDetail
from app.services import holds, shows
from app.services.auth import Auth, client_ip, holder_of, optional_auth

router = APIRouter(tags=["seat map"])

STREAMS_PER_NET = 6  # open at once: a few tabs and the landing demo, not a botnet's worth

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


@router.get(
    "/shows/{show_id}/stream",
    response_class=StreamingResponse,
    responses={
        200: {"content": {"text/event-stream": {}}, "description": "`snapshot` events"},
        503: {"description": "No live updates right now: poll `/seats`"},
    },
)
async def stream_seats(
    show_id: str,
    request: Request,
    response: Response,
    db: Db,
    auth: OptAuth,
    redis: Annotated[Redis, Depends(require_redis)],
) -> StreamingResponse:
    """Server-sent events: `snapshot` (a `SeatState`) at once and after every hold, release,
    sale or lapse; `closed` if the show is cancelled. Ends after a few minutes; EventSource
    reconnects on its own."""
    show, _, _, _ = await shows.load(db, show_id, datetime.now(UTC))
    await db.close()  # don't pin a pooled connection for minutes
    # The stream's first hold must land on the same holder as the page's (sets fr_sid if new).
    holder = holder_of(request, response, auth, create=True)

    async def reload_sold() -> tuple[list[str], list[str]]:
        async with side_session(request) as s:
            return await shows.taken_seats(s, show.id)

    return await event_stream(request, response, redis, show.id, holder, reload_sold)


async def event_stream(
    request: Request,
    response: Response,
    redis: Redis,
    show_key: uuid.UUID | str,
    holder: str | None,
    reload_sold: Callable[[], Awaitable[tuple[list[str], list[str]]]],
) -> StreamingResponse:
    """`shows.live_seats` as an SSE response, limited per network (opens a minute, and open at
    once), carrying any cookie the route set. Shared with the landing page's demo hall."""
    settings: Settings = request.app.state.settings
    net = shows.net_of(client_ip(request, settings))
    if net:  # an open stream is a held connection: cap how many one network opens and keeps
        await holds.rate_limit(redis, f"stream:{net}", settings.holds_per_minute)
    open_key = f"fr:streams:{net}"
    if net and not await holds.take_slot(redis, open_key, STREAMS_PER_NET, settings):
        raise ApiError(
            "rate_limited", "Too many live seat maps open from your network.", status=429
        )

    async def closed() -> None:
        if net:
            await holds.give_slot(redis, open_key)

    events = shows.live_seats(
        redis, show_key, holder, reload_sold, seconds=settings.stream_seconds, on_close=closed
    )
    out = StreamingResponse(
        events,
        media_type="text/event-stream",
        # no-transform: proxies (and Next's gzip) must pass events through, not buffer them
        headers={"Cache-Control": "no-store, no-transform", "X-Accel-Buffering": "no"},
    )
    for name, value in response.raw_headers:
        if name == b"set-cookie":
            out.raw_headers.append((name, value))
    return out


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
