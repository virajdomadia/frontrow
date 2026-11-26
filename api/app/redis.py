"""Redis client (Upstash in production, any Redis locally) — holds and version counters only.

Created lazily per app (like the DB engine) so the app imports and serves `/health` with no
`REDIS_URL` at all. Routes that *write* holds need it and answer 503 `unavailable` without it;
routes that only *read* hold counts degrade to "no holds" — Postgres stays the truth for sales
(04 §10: Redis down → holds fail with "try again", sales still confirm).

Every Frontrow key starts with `fr:` so one Upstash database can be shared with other apps
(Tripsmith also uses `otp:{email}`) without clashes.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from redis.asyncio import Redis

from app.config import Settings
from app.errors import ApiError

log = logging.getLogger(__name__)


def redis_for(app: FastAPI) -> Redis | None:
    client: Redis | None = getattr(app.state, "redis", None)
    if client is not None:
        return client
    settings: Settings = app.state.settings
    if settings.redis_url is None:
        return None
    client = Redis.from_url(
        settings.redis_url.get_secret_value(),
        decode_responses=True,
        socket_timeout=5,
        socket_connect_timeout=5,
        health_check_interval=30,
    )
    app.state.redis = client
    return client


async def close_redis(app: FastAPI) -> None:
    client: Redis | None = getattr(app.state, "redis", None)
    if client is not None:
        await client.aclose()
        app.state.redis = None


def optional_redis(request: Request) -> Redis | None:
    """FastAPI dependency for read paths: None when Redis isn't configured."""
    return redis_for(request.app)


def require_redis(request: Request) -> Redis:
    """FastAPI dependency for hold writes: 503 when Redis isn't configured."""
    client = redis_for(request.app)
    if client is None:
        raise ApiError("unavailable", "Seat holds are unavailable right now. Try again shortly.")
    return client
