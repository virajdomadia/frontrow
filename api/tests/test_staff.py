"""B11: staff keep the film catalogue, answer film requests and approve businesses (R11)."""

from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine

from app.seed import seed
from tests.helpers import code_sign_in, demo, tab

pytestmark = [pytest.mark.db, pytest.mark.redis]

STAFF = "boss@frontrow.example"
FILM = {
    "title": "Kaveri Express",
    "synopsis": "Two strangers share the last seats on a night bus from Mysuru to Bengaluru.",
    "cast_crew": [{"name": "Hamsa Rao", "role": "Director"}, {"name": "Dev Nair", "role": "Actor"}],
    "runtime_min": 121,
    "cert": "U",
    "genres": ["Drama"],
    "languages": ["Kannada"],
    "formats": ["2D"],
    "poster_url": "/img/posters/glass-city.jpg",
    "release_date": "2026-12-01",
    "status": "coming_soon",
}


async def test_catalogue_and_requests(db_engine: AsyncEngine, db_app: FastAPI) -> None:
    await seed(db_engine, now=datetime.now(UTC), staff=STAFF)
    async with tab(db_app) as staff, tab(db_app) as owner:
        await code_sign_in(db_app, staff, STAFF, door="staff", name=None)
        await demo(owner, "owner")
        counts = (await staff.get("/staff/counts")).json()
        assert counts == {"pending_businesses": 1, "open_requests": 2, "films": 8}

        films = (await staff.get("/staff/films")).json()
        assert len(films) == 8 and films[0]["status"] == "now_showing"
        assert any(f["scheduled_shows"] > 0 for f in films)

        requests = (await staff.get("/staff/film-requests", params={"status": "open"})).json()
        kaveri = next(r for r in requests if r["title"] == "Kaveri Express")
        assert kaveri["business"]["name"] == "Orbit Cinemas"

        bad = await staff.post(
            "/staff/films", json={**FILM, "poster_url": "https://evil.example/x.jpg"}
        )
        assert bad.status_code == 422
        made = await staff.post("/staff/films", json={**FILM, "request_id": kaveri["id"]})
        assert made.status_code == 201, made.text
        film = made.json()
        assert film["slug"] == "kaveri-express" and film["status"] == "coming_soon"

        # The owner sees the request answered with the film linked.
        mine = (await owner.get("/owner/film-requests")).json()
        answered = next(r for r in mine if r["title"] == "Kaveri Express")
        assert answered["status"] == "added" and answered["film"]["slug"] == "kaveri-express"

        # Now showing → it can be scheduled and shows on home once it has shows.
        edited = await staff.patch(
            f"/staff/films/{film['id']}", json={**FILM, "status": "now_showing", "runtime_min": 125}
        )
        assert edited.status_code == 200 and edited.json()["runtime_min"] == 125

        # Decline needs a reason.
        other = next(r for r in requests if r["title"] == "Monsoon Letters")
        no_reason = await staff.patch(
            f"/staff/film-requests/{other['id']}", json={"action": "decline"}
        )
        assert no_reason.status_code == 422
        declined = await staff.patch(
            f"/staff/film-requests/{other['id']}",
            json={"action": "decline", "reply": "No distributor confirmation yet"},
        )
        assert declined.status_code == 200 and declined.json()["status"] == "declined"
        twice = await staff.patch(
            f"/staff/film-requests/{other['id']}", json={"action": "decline", "reply": "x"}
        )
        assert twice.status_code == 409


async def test_approvals(db_engine: AsyncEngine, db_app: FastAPI) -> None:
    await seed(db_engine, now=datetime.now(UTC), staff=STAFF)
    async with tab(db_app) as staff:
        await code_sign_in(db_app, staff, STAFF, door="staff", name=None)
        [pending] = (await staff.get("/staff/businesses", params={"status": "pending"})).json()
        assert pending["name"] == "Lakeview Pictures"
        assert pending["owners"][0]["name"] == "Rhea Kapoor"
        assert pending["cinemas"][0]["screens"] == 1 and pending["scheduled_shows"] > 0

        reject = await staff.patch(f"/staff/businesses/{pending['id']}", json={"action": "reject"})
        assert reject.status_code == 422  # a rejection needs a reason
        rejected = await staff.patch(
            f"/staff/businesses/{pending['id']}",
            json={"action": "reject", "note": "Phone number didn't answer"},
        )
        assert rejected.json()["status"] == "rejected"
        assert rejected.json()["review_note"] == "Phone number didn't answer"
        approved = await staff.patch(
            f"/staff/businesses/{pending['id']}", json={"action": "approve"}
        )
        assert approved.json()["status"] == "verified" and approved.json()["verified_at"]
        home = (await staff.get("/films/the-last-dune")).json()
        assert home["show_count"] > 0

    async with tab(db_app) as customer:
        await demo(customer, "customer")
        assert (await customer.get("/staff/counts")).status_code == 403
        assert (await customer.post("/staff/films", json=FILM)).status_code == 403
