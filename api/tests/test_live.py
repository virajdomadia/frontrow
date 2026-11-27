"""L1: live seat updates. The stream generator against a real Redis (every change reaches an
open map in well under a second, a lapse too, and nothing is sent while idle), then the route
through the app (snapshot first, the holder cookie, closed shows, no Redis → poll)."""

import asyncio
import json
import time
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.models import Show
from app.models.enums import ShowStatus
from app.redis import close_redis, redis_for
from app.seed import seed
from app.services import holds, shows
from tests.helpers import open_show, tab

ST = uuid.uuid4()


def seat() -> str:
    return str(uuid.uuid4())


async def next_event(events: AsyncIterator[str]) -> tuple[str, dict]:
    async for chunk in events:
        if chunk.startswith("event: "):
            name = chunk.split("\n")[0][7:]
            data = next(line[6:] for line in chunk.split("\n") if line.startswith("data: "))
            return name, json.loads(data)
    raise AssertionError("stream ended")


@pytest.mark.redis
async def test_stream_pushes_every_change(app: FastAPI) -> None:
    redis = redis_for(app)
    assert redis is not None
    sold: list[str] = []

    async def reload() -> list[str]:
        return list(sold)

    events = shows.live_seats(redis, ST, "b", [], reload, seconds=8)
    name, first = await next_event(events)
    assert name == "snapshot" and first["held"] == [] and first["mine"] == []

    async def pushed() -> dict:
        t = time.monotonic()
        name, data = await asyncio.wait_for(next_event(events), 1.0)
        assert name == "snapshot" and time.monotonic() - t < 1.0
        return data

    f6, f7, f8 = seat(), seat(), seat()
    now = datetime.now(UTC)
    await holds.acquire(redis, ST, "a", [f7], ttl_seconds=60, now=now)
    assert [h["seat_id"] for h in (await pushed())["held"]] == [f7]

    await holds.release(redis, ST, "a", [f7])
    assert (await pushed())["held"] == []

    await holds.acquire(redis, ST, "b", [f6], ttl_seconds=60, now=now)
    mine = await pushed()
    assert mine["mine"] == [f6] and mine["held"] == []

    sold.append(f8)  # a sale commits, then clears holds and publishes "s"
    await holds.clear_sold(redis, ST, [f8])
    assert (await pushed())["sold"] == [f8]

    # A lapse bumps no version and publishes nothing: the stream wakes for the deadline itself.
    await holds.acquire(redis, ST, "a", [f7], ttl_seconds=1, now=datetime.now(UTC))
    assert [h["seat_id"] for h in (await pushed())["held"]] == [f7]
    lapsed = await asyncio.wait_for(next_event(events), 2.0)
    assert lapsed[1]["held"] == []

    await redis.publish(holds.channel(ST), "x")
    assert (await asyncio.wait_for(next_event(events), 1.0))[0] == "closed"
    with pytest.raises(StopAsyncIteration):
        await anext(events)


@pytest.mark.redis
async def test_stream_is_quiet_when_nothing_changes(
    app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Idle: pings only, and no Redis command at all (Upstash bills per command)."""
    redis = redis_for(app)
    assert redis is not None
    monkeypatch.setattr(shows, "PING_SECONDS", 0.1)

    async def reload() -> list[str]:
        raise AssertionError("no sale happened")

    events = shows.live_seats(redis, ST, None, [], reload, seconds=1.5)
    await next_event(events)
    before = (await redis.info("stats"))["total_commands_processed"]
    rest = [chunk async for chunk in events]
    after = (await redis.info("stats"))["total_commands_processed"]
    assert len(rest) >= 10 and all(c == ": ping\n\n" for c in rest)
    assert after - before <= 6  # INFO and closing the subscription: a constant, not per ping


@pytest.mark.db
@pytest.mark.redis
async def test_stream_route(db_engine: AsyncEngine, db: AsyncSession, db_app: FastAPI) -> None:
    db_app.state.settings = db_app.state.settings.model_copy(update={"stream_seconds": 1})
    await seed(db_engine, now=datetime.now(UTC))
    found = await open_show(db)
    url = f"/shows/{found.show.id}/stream"

    async with tab(db_app) as a, tab(db_app) as b:
        res = await a.get(url)
        assert res.status_code == 200
        assert res.headers["content-type"].startswith("text/event-stream")
        assert res.headers["cache-control"] == "no-store, no-transform"
        assert "fr_sid" in res.cookies  # the page's first hold lands on this holder
        name, data = await next_event(_chunks(res.text))
        assert name == "snapshot" and data["v"] >= 0 and data["mine"] == []

        # A hold made from tab B during A's stream shows in A's next snapshot.
        async def hold_soon() -> None:
            await asyncio.sleep(0.3)
            r = await b.post(
                f"/shows/{found.show.id}/holds", json={"seat_ids": [found.all_free[0]]}
            )
            assert r.status_code == 200

        res, _ = await asyncio.gather(a.get(url), hold_soon())
        snaps = [json.loads(line[6:]) for line in res.text.split("\n") if line.startswith("data: ")]
        assert any(found.all_free[0] in [h["seat_id"] for h in s["held"]] for s in snaps)

    await db.execute(
        update(Show).where(Show.id == found.show.id).values(status=ShowStatus.CANCELLED)
    )
    await db.commit()
    async with tab(db_app) as c:
        closed = await c.get(url)
        assert closed.status_code == 410 and closed.json()["error"]["code"] == "show_closed"


@pytest.mark.db
@pytest.mark.redis
async def test_stream_opens_limited_per_network(
    db_engine: AsyncEngine, db: AsyncSession, db_app: FastAPI
) -> None:
    db_app.state.settings = db_app.state.settings.model_copy(
        update={"stream_seconds": 0, "holds_per_minute": 3}
    )
    await seed(db_engine, now=datetime.now(UTC))
    found = await open_show(db)
    codes = []
    for _ in range(4):
        async with tab(db_app) as c:  # a fresh cookie each time doesn't help
            codes.append((await c.get(f"/shows/{found.show.id}/stream")).status_code)
    assert codes == [200, 200, 200, 429]


@pytest.mark.db
async def test_stream_needs_redis(
    db_engine: AsyncEngine, db: AsyncSession, db_app: FastAPI
) -> None:
    """No Redis → 503, and the web falls back to polling `/seats`."""
    await close_redis(db_app)
    db_app.state.settings = db_app.state.settings.model_copy(update={"redis_url": None})
    await seed(db_engine, now=datetime.now(UTC))
    found = await open_show(db)
    async with tab(db_app) as c:
        res = await c.get(f"/shows/{found.show.id}/stream")
        assert res.status_code == 503


async def _chunks(text: str) -> AsyncIterator[str]:
    for chunk in text.split("\n\n"):
        yield chunk + "\n\n"
