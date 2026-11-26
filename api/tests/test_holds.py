"""B5: the hold engine (04 §11) — the race, all-or-none, expiry — and the routes around it.

The engine tests run the real Lua against a real Redis (`TEST_REDIS_URL`); the route tests go
through the app with the seeded catalogue, so the two-tabs story is tested end to end: tab A
holds a seat, tab B sees it greyed and can't take it, A lets go, B can.
"""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.errors import ApiError
from app.models import Ticket
from app.redis import close_redis, redis_for
from app.seed import seed
from app.services import holds
from tests.conftest import TEST_HOLD_TTL
from tests.helpers import open_show, tab

ST = uuid.uuid4()


def seat() -> str:
    return str(uuid.uuid4())


# --- engine ---------------------------------------------------------------------------------------


@pytest.mark.redis
async def test_holds_concurrent(app: FastAPI) -> None:
    """20 holders race for one seat in the same instant: exactly one wins."""
    redis = redis_for(app)
    assert redis is not None
    f7 = seat()
    now = datetime.now(UTC)

    async def attempt(i: int) -> bool:
        try:
            await holds.acquire(redis, ST, f"tab-{i}", [f7], ttl_seconds=60, now=now)
            return True
        except ApiError as e:
            assert e.code == "seat_taken" and e.details == {"taken": [f7]}
            return False

    results = await asyncio.gather(*(attempt(i) for i in range(20)))
    assert results.count(True) == 1
    live = await holds.snapshot(redis, ST, None, now=now)
    assert [h.seat_id for h in live.others] == [f7] and live.v == 1


@pytest.mark.redis
async def test_holds_all_or_none(app: FastAPI) -> None:
    """A holds F7; B asks for F6 + F7 → 409 naming F7 only, and F6 stays free."""
    redis = redis_for(app)
    assert redis is not None
    f6, f7 = seat(), seat()
    now = datetime.now(UTC)
    await holds.acquire(redis, ST, "a", [f7], ttl_seconds=60, now=now)
    with pytest.raises(ApiError) as err:
        await holds.acquire(redis, ST, "b", [f6, f7], ttl_seconds=60, now=now)
    assert err.value.status == 409 and err.value.details == {"taken": [f7]}
    assert await redis.get(holds.hold_key(ST, f6)) is None

    # Re-tapping your own seat is fine, and adding one keeps the original deadline.
    first = await holds.acquire(redis, ST, "a", [f7], ttl_seconds=60, now=now)
    later = await holds.acquire(redis, ST, "a", [f7, f6], ttl_seconds=60, now=now)
    assert later.expires_at <= first.expires_at
    b_view = await holds.snapshot(redis, ST, "b", now=now)
    assert {h.seat_id for h in b_view.others} == {f6, f7} and b_view.mine == []
    a_view = await holds.snapshot(redis, ST, "a", now=now)
    assert set(a_view.mine) == {f6, f7} and a_view.others == []

    # Release is compare-and-delete: B can't release A's seat; A can.
    assert await holds.release(redis, ST, "b", [f7]) == 0
    assert await holds.release(redis, ST, "a", [f7]) == 1
    assert {h.seat_id for h in (await holds.snapshot(redis, ST, "b", now=now)).others} == {f6}


@pytest.mark.redis
async def test_hold_expiry(app: FastAPI) -> None:
    """TTL 1 s → the seat is free again after 1.2 s, for the engine and for the snapshot."""
    redis = redis_for(app)
    assert redis is not None
    f7 = seat()
    await holds.acquire(redis, ST, "a", [f7], ttl_seconds=1, now=datetime.now(UTC))
    await asyncio.sleep(1.2)
    now = datetime.now(UTC)
    assert (await holds.snapshot(redis, ST, None, now=now)).others == []
    assert await redis.hlen(holds.hash_key(ST)) == 0  # the stale mirror entry was pruned
    granted = await holds.acquire(redis, ST, "b", [f7], ttl_seconds=1, now=now)
    assert granted.held == [f7]


# --- routes ---------------------------------------------------------------------------------------


@pytest.mark.db
@pytest.mark.redis
async def test_two_tabs_one_seat(db_engine: AsyncEngine, db: AsyncSession, db_app: FastAPI) -> None:
    await seed(db_engine, now=datetime.now(UTC))
    found = await open_show(db)
    showtime, free = found.show, found.all_free
    f6, f7 = free[0], free[1]
    url = f"/shows/{showtime.id}"

    async with tab(db_app) as a, tab(db_app) as b:
        held = await a.post(f"{url}/holds", json={"seat_ids": [f7]})
        assert held.status_code == 200, held.text
        assert "fr_sid" in held.cookies
        expires = datetime.fromisoformat(held.json()["expires_at"])
        assert timedelta(0) < expires - datetime.now(UTC) <= timedelta(seconds=TEST_HOLD_TTL)

        mine = (await a.get(f"{url}/seats")).json()
        assert mine["mine"] == [f7] and mine["mine_expires_at"]
        theirs = (await b.get(f"{url}/seats")).json()
        assert [h["seat_id"] for h in theirs["held"]] == [f7] and theirs["mine"] == []
        assert theirs["v"] >= 1

        clash = await b.post(f"{url}/holds", json={"seat_ids": [f6, f7]})
        assert clash.status_code == 409
        assert clash.json()["error"] == {
            "code": "seat_taken",
            "message": "That seat was just taken",
            "details": {"taken": [f7]},
        }
        assert (await b.post(f"{url}/holds", json={"seat_ids": [f6]})).status_code == 200

        let_go = await a.request("DELETE", f"{url}/holds", json={"seat_ids": [f7]})
        assert let_go.status_code == 204
        assert (await b.post(f"{url}/holds", json={"seat_ids": [f6, f7]})).status_code == 200


@pytest.mark.db
@pytest.mark.redis
async def test_hold_rules(db_engine: AsyncEngine, db: AsyncSession, db_app: FastAPI) -> None:
    await seed(db_engine, now=datetime.now(UTC))
    found = await open_show(db)
    showtime, free = found.show, found.all_free
    url = f"/shows/{showtime.id}/holds"
    sold = await db.scalar(select(Ticket.seat_id).where(Ticket.show_id == showtime.id))

    async with tab(db_app) as a:
        too_many = await a.post(url, json={"seat_ids": free[:11]})
        assert too_many.status_code == 422
        assert too_many.json()["error"]["code"] == "too_many_seats"

        sold_res = await a.post(url, json={"seat_ids": [str(sold)]})
        assert sold_res.status_code == 409
        assert sold_res.json()["error"]["details"] == {"taken": [str(sold)]}

        stranger = await a.post(url, json={"seat_ids": [str(uuid.uuid4())]})
        assert stranger.status_code == 422

        # Ten in one tab, then an eleventh from the same holder: still capped.
        assert (await a.post(url, json={"seat_ids": free[:10]})).status_code == 200
        assert (await a.post(url, json={"seat_ids": [free[10]]})).status_code == 422


@pytest.mark.db
@pytest.mark.redis
async def test_holds_rate_limited(
    db_engine: AsyncEngine, db: AsyncSession, db_app: FastAPI
) -> None:
    await seed(db_engine, now=datetime.now(UTC))
    found = await open_show(db)
    showtime, free = found.show, found.all_free
    url = f"/shows/{showtime.id}/holds"
    async with tab(db_app) as a:
        codes = [(await a.post(url, json={"seat_ids": [free[0]]})).status_code for _ in range(31)]
    assert codes[:30] == [200] * 30 and codes[30] == 429


@pytest.mark.db
async def test_holds_need_redis(db_engine: AsyncEngine, db: AsyncSession, db_app: FastAPI) -> None:
    """No Redis → holds are a 503 "try again"; the seat map still reads (sold only)."""
    await close_redis(db_app)
    db_app.state.settings = db_app.state.settings.model_copy(update={"redis_url": None})
    await seed(db_engine, now=datetime.now(UTC))
    found = await open_show(db)
    showtime, free = found.show, found.all_free
    async with tab(db_app) as a:
        res = await a.post(f"/shows/{showtime.id}/holds", json={"seat_ids": [free[0]]})
        assert res.status_code == 503 and res.json()["error"]["code"] == "unavailable"
        seats = await a.get(f"/shows/{showtime.id}/seats")
        assert seats.status_code == 200 and seats.json()["held"] == []
