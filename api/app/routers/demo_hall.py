"""'Try it live' on the landing page (L2): two people, one small hall, side by side.

Each visitor gets a private sandbox hall keyed on their `fr_sid`, held in Redis only: no show,
no Postgres row, nobody else's seats. The two maps are two holders in it (`a` = you, `b` = the
other person), and the holds run through the real engine: the same Lua (all or none, one
deadline per holder, publish on change) and the same live stream as a real seat map. Holds here
last 45 s so a visitor sees one lapse; every sandbox key expires within the hour.
"""

import hashlib
import time
import uuid
from datetime import UTC, datetime
from functools import cache
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import Field
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.config import Settings
from app.errors import ApiError
from app.redis import require_redis
from app.routers.shows import event_stream
from app.schemas import ApiModel
from app.schemas.layouts import GridKnobs, TierBand
from app.schemas.shows import HoldGranted, SeatState
from app.services import holds, layouts, shows
from app.services.auth import client_ip, holder_of

router = APIRouter(prefix="/demo/hall", tags=["try it live"])

TTL_SECONDS = 45
KEEP_SECONDS = 3600  # a sandbox's hash and version counter outlive its last hold by an hour
SEAT_NS = uuid.UUID("7d1f9a52-30c4-4f0b-9a57-6a2f3f0c1e11")


@cache
def hall() -> tuple[dict[str, Any], frozenset[str]]:
    """A small grid (8 rows of 10, fits a phone) with stable seat ids, the same for everyone."""
    gen = layouts.generate(
        GridKnobs(
            rows=8,
            seats_per_row=10,
            aisle_after=5,
            tiers=[
                TierBand(key="classic", label="Classic", rows=5),
                TierBand(key="prime", label="Prime", rows=3),
            ],
        )
    )
    ids = {
        key: str(uuid.uuid5(SEAT_NS, f"{key[0]}:{key[1]}:{key[2]}"))
        for key, *_ in layouts.seat_rows(gen)
    }
    return layouts.layout_json(gen, ids), frozenset(ids.values())


class DemoHall(ApiModel):
    layout: dict[str, Any]
    seats: SeatState = Field(description="As seen by `a` (you): `mine` = a's, `held` = b's.")
    ttl_seconds: int


class DemoHold(ApiModel):
    as_: Literal["a", "b"] = Field(alias="as")
    seat_ids: list[str] = Field(min_length=1, max_length=holds.MAX_SEATS)


def _sandbox(request: Request, response: Response) -> tuple[str, str]:
    """(sandbox id, its key for holders and limits) from the `fr_sid` cookie alone: no session
    lookup, so the demo never touches Postgres. Both are a hash, so the client-supplied cookie
    never reaches a key or a hold value raw."""
    sid = holder_of(request, response, None, create=True)
    assert sid is not None
    box = "demo-" + hashlib.sha256(sid.encode()).hexdigest()[:24]
    return box, box


async def _limit(redis: Redis, request: Request, sid: str) -> None:
    settings: Settings = request.app.state.settings
    await holds.rate_limit(redis, f"demo:{sid}", settings.holds_per_minute)
    net = shows.net_of(client_ip(request, settings))
    if net:  # rotating the cookie doesn't reset this one
        await holds.rate_limit(redis, f"demo:ip:{net}", 2 * settings.holds_per_minute)


async def _keep(redis: Redis, box: str) -> None:
    try:
        async with redis.pipeline(transaction=False) as pipe:
            pipe.expire(holds.hash_key(box), KEEP_SECONDS)
            pipe.expire(holds.version_key(box), KEEP_SECONDS)
            await pipe.execute()
    except RedisError as e:
        raise ApiError("unavailable", "The demo hall is unavailable right now.") from e


async def _state(redis: Redis, box: str, sid: str) -> SeatState:
    now = datetime.now(UTC)
    return shows.state_of([], await holds.snapshot(redis, box, f"{sid}:a", now=now), now)


@router.get("", response_model=DemoHall)
async def get_hall(
    request: Request,
    response: Response,
    redis: Annotated[Redis, Depends(require_redis)],
) -> DemoHall:
    response.headers["Cache-Control"] = "no-store"
    box, sid = _sandbox(request, response)
    return DemoHall(layout=hall()[0], seats=await _state(redis, box, sid), ttl_seconds=TTL_SECONDS)


@router.get("/seats", response_model=SeatState)
async def get_seats(
    request: Request,
    response: Response,
    redis: Annotated[Redis, Depends(require_redis)],
) -> SeatState:
    """The polling fallback for the stream."""
    response.headers["Cache-Control"] = "no-store"
    box, sid = _sandbox(request, response)
    return await _state(redis, box, sid)


@router.get("/stream", response_class=StreamingResponse)
async def stream(
    request: Request,
    response: Response,
    redis: Annotated[Redis, Depends(require_redis)],
) -> StreamingResponse:
    """The same live stream as a real seat map (`/shows/{id}/stream`), on the sandbox."""
    box, sid = _sandbox(request, response)

    async def no_sales() -> list[str]:
        return []

    return await event_stream(request, response, redis, box, f"{sid}:a", no_sales)


@router.post("/holds", response_model=HoldGranted)
async def place(
    body: DemoHold,
    request: Request,
    response: Response,
    redis: Annotated[Redis, Depends(require_redis)],
) -> HoldGranted:
    """Hold for `a` or `b`: the whole selection or nothing, like a real hold."""
    box, sid = _sandbox(request, response)
    known = hall()[1]
    ids = list(dict.fromkeys(body.seat_ids))
    if any(i not in known for i in ids):
        raise ApiError("validation", "Unknown seat", details={"fields": {"seat_ids": "unknown"}})
    await _limit(redis, request, sid)
    try:  # an hour idle expires the counter: restart it above anything a map has seen
        await redis.set(holds.version_key(box), int(time.time() * 1000), nx=True)
    except RedisError as e:
        raise ApiError("unavailable", "The demo hall is unavailable right now.") from e
    granted = await holds.acquire(
        redis, box, f"{sid}:{body.as_}", ids, ttl_seconds=TTL_SECONDS, now=datetime.now(UTC)
    )
    await _keep(redis, box)
    return HoldGranted(expires_at=granted.expires_at, held=granted.held)


@router.delete("/holds", status_code=204)
async def drop(
    body: DemoHold,
    request: Request,
    response: Response,
    redis: Annotated[Redis, Depends(require_redis)],
) -> None:
    box, sid = _sandbox(request, response)
    await _limit(redis, request, sid)
    await holds.release(redis, box, f"{sid}:{body.as_}", list(dict.fromkeys(body.seat_ids)))
