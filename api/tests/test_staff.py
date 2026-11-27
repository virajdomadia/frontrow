"""B11: staff keep the film catalogue, answer film requests and approve businesses (R11)."""

from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine

from app.seed import seed
from tests.helpers import code_sign_in, demo, tab

pytestmark = [pytest.mark.db, pytest.mark.redis]

STAFF = "boss@frontrow.example"
# Answers the seeded request for it. Not certified and no runtime yet: both may be left out.
FILM = {
    "title": "Jumanji: Open World",
    "synopsis": "The players are pulled back into the game for one more adventure.",
    "cast_crew": [
        {"name": "Jake Kasdan", "role": "Director"},
        {"name": "Dwayne Johnson", "role": "Actor"},
    ],
    "genres": ["Adventure", "Comedy"],
    "languages": ["English", "Hindi", "Tamil", "Telugu"],
    "formats": ["2D", "3D"],
    "poster_url": "/img/posters/king.png",
    "release_date": "2026-12-25",
    "status": "coming_soon",
}


async def test_catalogue_and_requests(db_engine: AsyncEngine, db_app: FastAPI) -> None:
    await seed(db_engine, now=datetime.now(UTC), staff=STAFF)
    async with tab(db_app) as staff, tab(db_app) as owner:
        await code_sign_in(db_app, staff, STAFF, door="staff", name=None)
        await demo(owner, "owner")
        counts = (await staff.get("/staff/counts")).json()
        assert counts == {"pending_businesses": 1, "open_requests": 2, "films": 11}

        films = (await staff.get("/staff/films")).json()
        assert len(films) == 11 and films[0]["status"] == "now_showing"
        assert any(f["scheduled_shows"] > 0 for f in films)

        requests = (await staff.get("/staff/film-requests", params={"status": "open"})).json()
        jumanji = next(r for r in requests if r["title"] == "Jumanji: Open World")
        assert jumanji["business"]["name"] == "Orbit Cinemas"

        bad = await staff.post(
            "/staff/films", json={**FILM, "poster_url": "https://evil.example/x.jpg"}
        )
        assert bad.status_code == 422
        bad_cert = await staff.post("/staff/films", json={**FILM, "cert": "PG-13"})
        assert bad_cert.status_code == 422
        made = await staff.post("/staff/films", json={**FILM, "request_id": jumanji["id"]})
        assert made.status_code == 201, made.text
        film = made.json()
        assert film["slug"] == "jumanji-open-world" and film["status"] == "coming_soon"
        assert film["cert"] is None and film["runtime_min"] is None

        # The owner sees the request answered with the film linked.
        mine = (await owner.get("/owner/film-requests")).json()
        answered = next(r for r in mine if r["title"] == "Jumanji: Open World")
        assert answered["status"] == "added" and answered["film"]["slug"] == "jumanji-open-world"

        # Now showing → it can be scheduled and shows on home once it has shows.
        edited = await staff.patch(
            f"/staff/films/{film['id']}",
            json={**FILM, "status": "now_showing", "runtime_min": 125, "cert": "UA 7+"},
        )
        assert edited.status_code == 200, edited.text
        assert edited.json()["runtime_min"] == 125 and edited.json()["cert"] == "UA 7+"

        # Decline needs a reason.
        other = next(r for r in requests if r["title"] == "Gunmaaster G9")
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
        home = (await staff.get("/films/yeh-prem-mol-liya")).json()
        assert home["show_count"] > 0

    async with tab(db_app) as customer:
        await demo(customer, "customer")
        assert (await customer.get("/staff/counts")).status_code == 403
        assert (await customer.post("/staff/films", json=FILM)).status_code == 403
