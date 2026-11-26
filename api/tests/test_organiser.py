"""F7/F8: the organiser console — a new organiser goes from sign-up to a bookable showtime;
ownership is enforced; a showtime with sales can't be cancelled; bookings list + CSV."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine

from app.seed import seed

pytestmark = pytest.mark.db

GRID = {
    "template": "grid",
    "rows": 8,
    "seats_per_row": 12,
    "aisle_after": 6,
    "tiers": [
        {"key": "regular", "label": "Regular", "rows": 6},
        {"key": "gold", "label": "Gold", "rows": 2},
    ],
}


def tab(app: FastAPI) -> AsyncClient:
    return AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test"
    )


async def test_sign_up_to_bookable_showtime(db_app: FastAPI) -> None:
    async with tab(db_app) as c:
        up = await c.post(
            "/auth/sign-up",
            json={
                "email": "hall@example.com",
                "password": "password1",
                "name": "Lumen Hall",
                "role": "organiser",
            },
        )
        assert up.json()["role"] == "organiser"

        preview = await c.post("/organiser/venues/preview", json={"knobs": GRID})
        assert preview.status_code == 200
        assert sum(len(r["seats"]) for s in preview.json()["sections"] for r in s["rows"]) == 96
        bad = await c.post("/organiser/venues/preview", json={"knobs": {**GRID, "rows": 9}})
        assert bad.status_code == 422  # tier bands must cover the rows

        venue = await c.post(
            "/organiser/venues",
            json={"name": "Lumen Hall", "address": "12 Church Street, Bengaluru", "knobs": GRID},
        )
        assert venue.status_code == 201 and venue.json()["seat_count"] == 96

        event = await c.post(
            "/organiser/events",
            json={
                "title": "Neon Alley",  # clashes with a seeded slug? not here — fresh db
                "type": "movie",
                "genre": "Thriller",
                "duration_min": 120,
                "synopsis": "A late-night premiere screening with a Q&A after.",
                "poster_url": "/img/posters/glass-city.jpg",
            },
        )
        assert event.status_code == 201 and event.json()["status"] == "live"
        assert event.json()["slug"] == "neon-alley"
        bad_poster = await c.post(
            "/organiser/events",
            json={**event.json(), "poster_url": "https://evil.example/x.jpg"},
        )
        assert bad_poster.status_code == 422

        starts = (datetime.now(UTC) + timedelta(days=2)).isoformat()
        showtime = await c.post(
            "/organiser/showtimes",
            json={
                "event_id": event.json()["id"],
                "venue_id": venue.json()["id"],
                "starts_at": starts,
                "tiers": [
                    {"tier_key": "regular", "price_paise": 25000},
                    {"tier_key": "gold", "price_paise": 45000},
                ],
            },
        )
        assert showtime.status_code == 201, showtime.text
        st = showtime.json()
        assert [t["label"] for t in st["tiers"]] == ["Regular", "Gold"] and st["sold"] == 0

        # Bookable: the public seat map serves it straight away.
        public = await c.get(f"/showtimes/{st['id']}")
        assert public.status_code == 200 and public.json()["seats_left"] == 96
        listed = await c.get("/events/neon-alley")
        assert listed.status_code == 200 and len(listed.json()["showtimes"]) == 1

        # A second event with the same title gets its own slug.
        again = await c.post("/organiser/events", json={**event.json(), "status": "draft"})
        assert again.json()["slug"] == "neon-alley-2"

        # No sales yet → it can move and be cancelled.
        moved = await c.patch(
            f"/organiser/showtimes/{st['id']}",
            json={"starts_at": (datetime.now(UTC) + timedelta(days=3)).isoformat()},
        )
        assert moved.status_code == 200
        cancelled = await c.patch(f"/organiser/showtimes/{st['id']}", json={"status": "cancelled"})
        assert cancelled.json()["status"] == "cancelled"
        assert (await c.get(f"/showtimes/{st['id']}")).status_code == 410


async def test_ownership_sales_guard_and_bookings(db_engine: AsyncEngine, db_app: FastAPI) -> None:
    await seed(db_engine, now=datetime.now(UTC))
    async with tab(db_app) as org:
        await org.post("/auth/demo", json={"as": "organiser"})
        venues = (await org.get("/organiser/venues")).json()
        assert {v["template"] for v in venues} == {"grid", "stalls_balcony", "arena"}
        events = (await org.get("/organiser/events")).json()
        assert len(events) == 8 and all(e["tickets_sold"] > 0 for e in events)
        showtimes = (await org.get("/organiser/showtimes")).json()
        sold = next(s for s in showtimes if s["sold"] > 0)
        assert sold["revenue_paise"] > 0

        blocked = await org.patch(
            f"/organiser/showtimes/{sold['id']}", json={"status": "cancelled"}
        )
        assert blocked.status_code == 409 and blocked.json()["error"]["code"] == "has_sales"

        booked = await org.get(f"/organiser/showtimes/{sold['id']}/bookings")
        assert booked.status_code == 200
        data = booked.json()
        assert data["tickets"] == sold["sold"] and data["bookings"][0]["customer_email"]
        csv = await org.get(f"/organiser/showtimes/{sold['id']}/bookings?format=csv")
        assert csv.headers["content-type"].startswith("text/csv")
        assert "attachment" in csv.headers["content-disposition"]
        lines = csv.text.strip().splitlines()
        assert (
            lines[0].startswith("order_id,paid_at,customer")
            and len(lines) == len(data["bookings"]) + 1
        )

    async with tab(db_app) as rival:
        await rival.post(
            "/auth/sign-up",
            json={
                "email": "rival@example.com",
                "password": "password1",
                "name": "Rival",
                "role": "organiser",
            },
        )
        assert (await rival.get("/organiser/venues")).json() == []
        assert (await rival.get(f"/organiser/showtimes/{sold['id']}/bookings")).status_code == 404
        assert (await rival.get(f"/organiser/venues/{venues[0]['id']}")).status_code == 404
        hijack = await rival.patch(
            f"/organiser/events/{events[0]['id']}", json={"title": "Mine now"}
        )
        assert hijack.status_code == 404
