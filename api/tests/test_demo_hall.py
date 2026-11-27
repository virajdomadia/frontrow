"""L2: the landing page's 'Try it live' hall. Two holders in a private Redis sandbox: the real
engine (all or none, live stream), nothing in Postgres, nothing shared between visitors."""

import json

import pytest
from fastapi import FastAPI

from app.redis import redis_for
from app.routers import demo_hall
from app.services import holds
from tests.helpers import tab


def seats(n: int) -> list[str]:
    return sorted(demo_hall.hall()[1])[:n]


@pytest.mark.redis
async def test_two_sides_one_seat(app: FastAPI) -> None:
    a1, a2 = seats(2)
    async with tab(app) as c:
        hall = (await c.get("/demo/hall")).json()
        assert hall["ttl_seconds"] == demo_hall.TTL_SECONDS
        assert hall["seats"] == {**hall["seats"], "mine": [], "held": [], "sold": []}

        assert (
            await c.post("/demo/hall/holds", json={"as": "a", "seat_ids": [a1]})
        ).status_code == 200
        taken = await c.post("/demo/hall/holds", json={"as": "b", "seat_ids": [a2, a1]})
        assert taken.status_code == 409 and taken.json()["error"]["details"] == {"taken": [a1]}
        assert (
            await c.post("/demo/hall/holds", json={"as": "b", "seat_ids": [a2]})
        ).status_code == 200

        state = (await c.get("/demo/hall/seats")).json()
        assert state["mine"] == [a1] and [h["seat_id"] for h in state["held"]] == [a2]

        # B can't let go of A's seat; A can.
        await c.request("DELETE", "/demo/hall/holds", json={"as": "b", "seat_ids": [a1]})
        assert (await c.get("/demo/hall/seats")).json()["mine"] == [a1]
        await c.request("DELETE", "/demo/hall/holds", json={"as": "a", "seat_ids": [a1]})
        assert (await c.get("/demo/hall/seats")).json()["mine"] == []

    # Another visitor has their own hall: B's seat is free there.
    async with tab(app) as other:
        assert (await other.get("/demo/hall/seats")).json()["held"] == []
        assert (
            await other.post("/demo/hall/holds", json={"as": "a", "seat_ids": [a2]})
        ).status_code == 200


@pytest.mark.redis
async def test_sandbox_rules(app: FastAPI) -> None:
    redis = redis_for(app)
    assert redis is not None
    async with tab(app) as c:
        unknown = await c.post("/demo/hall/holds", json={"as": "a", "seat_ids": ["not-a-seat"]})
        assert unknown.status_code == 422
        bad_side = await c.post("/demo/hall/holds", json={"as": "c", "seat_ids": seats(1)})
        assert bad_side.status_code == 422
        many = await c.post("/demo/hall/holds", json={"as": "a", "seat_ids": seats(11)})
        assert many.status_code == 422

        ok = await c.post("/demo/hall/holds", json={"as": "a", "seat_ids": seats(2)})
        assert ok.status_code == 200
        # Every sandbox key expires: nothing piles up in the shared Upstash database.
        keys = [k async for k in redis.scan_iter("fr:*demo-*")]
        ttls = [await redis.ttl(k) for k in keys]
        assert keys and all(0 < t <= demo_hall.KEEP_SECONDS for t in ttls)


@pytest.mark.redis
async def test_demo_hall_streams(app: FastAPI) -> None:
    app.state.settings = app.state.settings.model_copy(update={"stream_seconds": 1})
    async with tab(app) as c:
        await c.post("/demo/hall/holds", json={"as": "b", "seat_ids": seats(1)})
        res = await c.get("/demo/hall/stream")
        assert res.status_code == 200 and res.headers["content-type"].startswith(
            "text/event-stream"
        )
        first = next(line for line in res.text.split("\n") if line.startswith("data: "))
        assert [h["seat_id"] for h in json.loads(first[6:])["held"]] == seats(1)


def test_hall_is_stable() -> None:
    layout, ids = demo_hall.hall()
    assert len(ids) == 8 * 10 and holds.MAX_SEATS == 10
    assert {s["id"] for sec in layout["sections"] for r in sec["rows"] for s in r["seats"]} == ids
