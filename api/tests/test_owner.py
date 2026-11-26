"""B8–B10: a theatre owner from registration to a bookable show; bulk scheduling with the overlap
rule (04 §11 `test_show_overlap`); bookings + CSV; the door (`test_checkin`)."""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.models import Business, Film, Screen, Show
from app.seed import seed
from app.services.schedules import IST
from tests.helpers import code_sign_in, demo, open_show, signed_in, tab

pytestmark = [pytest.mark.db, pytest.mark.redis]

GRID = {
    "template": "grid",
    "rows": 10,
    "seats_per_row": 14,
    "aisle_after": 7,
    "tiers": [
        {"key": "classic", "label": "Classic", "rows": 7},
        {"key": "prime", "label": "Prime", "rows": 3},
    ],
}


def tomorrow() -> str:
    return (datetime.now(UTC).astimezone(IST).date() + timedelta(days=1)).isoformat()


async def test_register_to_bookable_show(
    db_engine: AsyncEngine, db: AsyncSession, db_app: FastAPI
) -> None:
    """A new owner sets up a cinema with two screens, schedules a film, and it goes public the
    moment staff approve the business (R8/R9/R11)."""
    await seed(db_engine, now=datetime.now(UTC), staff="boss@frontrow.example")
    film = await db.scalar(select(Film).where(Film.slug == "hollowmere"))
    assert film is not None
    async with tab(db_app) as owner:
        await code_sign_in(
            db_app, owner, "lata@sunrise.example", door="business", name="Lata",
            business={"name": "Sunrise Talkies", "phone": "+91 80 1234 5678"},
        )  # fmt: skip
        cinema = await owner.post(
            "/owner/cinemas",
            json={
                "name": "Sunrise Talkies",
                "area": "Jayanagar",
                "address": "11th Main, 4th Block, Jayanagar, Bengaluru",
                "facilities": ["Dolby Atmos", "Parking"],
                "photo_url": "/img/cinemas/cadence-hall.jpg",
            },
        )
        assert cinema.status_code == 201, cinema.text
        cid = cinema.json()["id"]
        dupe = await owner.post(
            "/owner/cinemas",
            json={"name": "sunrise talkies", "area": "X area", "address": "Somewhere 1"},
        )
        assert dupe.status_code == 409

        preview = await owner.post("/owner/screens/preview", json={"knobs": GRID})
        assert preview.status_code == 200 and len(preview.json()["sections"]) == 2
        one = await owner.post(
            f"/owner/cinemas/{cid}/screens",
            json={"name": "Screen 1", "formats": ["2D", "3D"], "knobs": GRID},
        )
        two = await owner.post(
            f"/owner/cinemas/{cid}/screens",
            json={
                "name": "Balcony hall",
                "formats": ["2D"],
                "knobs": {"template": "stalls_balcony"},
            },
        )
        assert one.status_code == 201 and two.status_code == 201, two.text
        assert one.json()["seat_count"] == 140
        listing = (await owner.get("/owner/cinemas")).json()
        assert [s["name"] for s in listing[0]["screens"]] == ["Screen 1", "Balcony hall"]

        made = await owner.post(
            "/owner/shows/bulk",
            json={
                "screen_id": one.json()["id"], "film_id": str(film.id), "language": "Kannada",
                "format": "3D", "days": [0, 1, 2, 3, 4, 5, 6], "times": ["10:00", "13:30"],
                "from_date": tomorrow(), "to_date": tomorrow(),
                "prices": {"classic": 15000, "prime": 21000},
            },
        )  # fmt: skip
        assert made.status_code == 201, made.text
        assert made.json()["created"] == 2
        assert all(s["public"] is False for s in made.json()["shows"])

        # Not public while the business is pending.
        shows = (
            await owner.get(
                "/films/hollowmere/shows",
                params={"date": tomorrow(), "language": "Kannada", "format": "3D"},
            )
        ).json()
        assert not any(c["name"] == "Sunrise Talkies" for c in shows["cinemas"])
        day = await owner.get("/owner/shows", params={"date": tomorrow()})
        assert len(day.json()["shows"]) == 2

    async with tab(db_app) as staff:
        await code_sign_in(db_app, staff, "boss@frontrow.example", door="staff", name=None)
        biz = await db.scalar(select(Business).where(Business.slug == "sunrise-talkies"))
        assert biz is not None
        res = await staff.patch(f"/staff/businesses/{biz.id}", json={"action": "approve"})
        assert res.status_code == 200 and res.json()["status"] == "verified"

    async with tab(db_app) as visitor:
        shows = (
            await visitor.get(
                "/films/hollowmere/shows",
                params={"date": tomorrow(), "language": "Kannada", "format": "3D"},
            )
        ).json()
        [sunrise] = [c for c in shows["cinemas"] if c["name"] == "Sunrise Talkies"]
        assert [s["screen_name"] for s in sunrise["shows"]] == ["Screen 1", "Screen 1"]


async def test_show_overlap(db_engine: AsyncEngine, db: AsyncSession, db_app: FastAPI) -> None:
    """Shows on one screen may not overlap (runtime + cleaning gap); the clash is named."""
    await seed(db_engine, now=datetime.now(UTC))
    screen = await db.scalar(select(Screen).where(Screen.name == "Screen 2"))
    film = await db.scalar(select(Film).where(Film.slug == "neon-alley"))
    assert screen is not None and film is not None
    base = {
        "screen_id": str(screen.id), "film_id": str(film.id), "language": "Hindi",
        "format": "2D", "days": [0, 1, 2, 3, 4, 5, 6], "from_date": tomorrow(),
        "to_date": tomorrow(), "prices": {"classic": 15000, "prime": 21000},
    }  # fmt: skip
    async with tab(db_app) as owner:
        await demo(owner, "owner")
        # Screen 2 shows Glass City at 17:30 every day (seeded, open-ended).
        clash = await owner.post("/owner/shows/bulk", json={**base, "times": ["16:00"]})
        assert clash.status_code == 409, clash.text
        err = clash.json()["error"]
        assert err["code"] == "overlap" and err["details"]["show"]["film_title"] == "Glass City"
        assert "Glass City" in err["message"]

        # Two times closer together than the runtime → refused before anything is created.
        tight = await owner.post("/owner/shows/bulk", json={**base, "times": ["09:00", "10:30"]})
        assert tight.status_code == 409

        bad_tiers = await owner.post(
            "/owner/shows/bulk", json={**base, "times": ["10:00"], "prices": {"classic": 15000}}
        )
        assert bad_tiers.status_code == 422
        bad_format = await owner.post(
            "/owner/shows/bulk", json={**base, "times": ["10:00"], "format": "IMAX"}
        )
        assert bad_format.status_code == 422
        bad_lang = await owner.post(
            "/owner/shows/bulk", json={**base, "times": ["10:00"], "language": "Tamil"}
        )
        assert bad_lang.status_code == 422

        ok = await owner.post("/owner/shows/bulk", json={**base, "times": ["10:00"]})
        assert ok.status_code == 201, ok.text
        again = await owner.post("/owner/shows/bulk", json={**base, "times": ["11:00"]})
        assert again.status_code == 409
        assert again.json()["error"]["details"]["show"]["film_title"] == "Neon Alley"


async def test_ownership_is_private(
    db_engine: AsyncEngine, db: AsyncSession, db_app: FastAPI
) -> None:
    """Another business's cinema, screen or show doesn't exist for you (404)."""
    await seed(db_engine, now=datetime.now(UTC))
    other = await db.scalar(select(Screen).where(Screen.name == "Audi 1"))  # Nandi Screens
    assert other is not None
    async with tab(db_app) as owner:
        await demo(owner, "owner")
        assert (await owner.get(f"/owner/screens/{other.id}")).status_code == 404
        assert (await owner.get(f"/owner/cinemas/{other.cinema_id}")).status_code == 404
        film = await db.scalar(select(Film).where(Film.slug == "undertow"))
        assert film is not None
        res = await owner.post(
            "/owner/shows/bulk",
            json={
                "screen_id": str(other.id), "film_id": str(film.id), "language": "English",
                "format": "2D", "days": [1], "times": ["08:00"], "from_date": tomorrow(),
                "to_date": tomorrow(), "prices": {"classic": 1, "prime": 1},
            },
        )  # fmt: skip
        assert res.status_code in (404, 422)
        mine = (await owner.get("/owner/shows")).json()
        assert all("Orbit" in s["cinema_name"] for s in mine["shows"])


async def test_film_requests(db_engine: AsyncEngine, db_app: FastAPI) -> None:
    await seed(db_engine, now=datetime.now(UTC))
    async with tab(db_app) as owner:
        await demo(owner, "owner")
        exists = await owner.post("/owner/film-requests", json={"title": "neon alley"})
        assert exists.status_code == 409  # already in the catalogue
        made = await owner.post(
            "/owner/film-requests", json={"title": "Bengaluru Blues", "note": "Kannada, 2D"}
        )
        assert made.status_code == 201 and made.json()["status"] == "open"
        titles = [r["title"] for r in (await owner.get("/owner/film-requests")).json()]
        assert titles[0] == "Bengaluru Blues" and "Kaveri Express" in titles


async def test_bookings_and_csv(db_engine: AsyncEngine, db: AsyncSession, db_app: FastAPI) -> None:
    await seed(db_engine, now=datetime.now(UTC))
    found = await open_show(db)  # 3-tier grid screens are all Orbit's: the demo owner's
    seats = found.free["prime"][:2]
    async with signed_in(db_app, "zoya") as c:
        await c.post(f"/shows/{found.show.id}/holds", json={"seat_ids": seats})
        order = (
            await c.post("/orders", json={"show_id": str(found.show.id), "seat_ids": seats})
        ).json()
        assert (await c.post(f"/orders/{order['id']}/demo-pay")).json()["status"] == "paid"
    async with tab(db_app) as owner:
        await demo(owner, "owner")
        res = await owner.get(f"/owner/shows/{found.show.id}/bookings")
        assert res.status_code == 200, res.text
        data = res.json()
        [mine] = [b for b in data["bookings"] if b["email"] == "zoya@example.com"]
        assert mine["name"] == "Zoya" and len(mine["seats"]) == 2
        assert mine["payment_method"] == "Test payment"
        assert data["show"]["sold"] >= 2 and data["show"]["revenue_paise"] > 0
        csv = await owner.get(f"/owner/shows/{found.show.id}/bookings", params={"format": "csv"})
        assert csv.headers["content-type"].startswith("text/csv")
        assert "zoya@example.com" in csv.text and csv.text.startswith("booking_id,name,email")

    from app.services.owner import csv_safe

    assert csv_safe("=HYPERLINK(1)") == "'=HYPERLINK(1)" and csv_safe("Zoya") == "Zoya"


async def test_checkin(db_engine: AsyncEngine, db: AsyncSession, db_app: FastAPI) -> None:
    """Valid once; second scan "already checked in"; wrong show; not a ticket; and two ushers
    scanning one ticket at the same instant admit it once."""
    await seed(db_engine, now=datetime.now(UTC))
    found = await open_show(db)
    seats = found.free["classic"][:2]
    async with signed_in(db_app) as c:  # demo customer
        await c.post(f"/shows/{found.show.id}/holds", json={"seat_ids": seats})
        order = (
            await c.post("/orders", json={"show_id": str(found.show.id), "seat_ids": seats})
        ).json()
        await c.post(f"/orders/{order['id']}/demo-pay")
        tickets = (await c.get(f"/tickets/{order['id']}")).json()["tickets"]
    a, b = tickets[0]["qr_token"], tickets[1]["qr_token"]
    show_id = str(found.show.id)
    async with tab(db_app) as usher, tab(db_app) as usher2:
        await demo(usher, "owner")
        await demo(usher2, "owner")
        first = await usher.post("/checkin", json={"token": a, "show_id": show_id})
        assert first.json()["result"] == "valid" and first.json()["seat"] == tickets[0]["label"]
        assert first.json()["admitted"] >= 1
        again = (await usher.post("/checkin", json={"token": a, "show_id": show_id})).json()
        assert again["result"] == "used" and again["message"].startswith("Already checked in at")
        junk = (
            await usher.post("/checkin", json={"token": "not-a-real-token", "show_id": show_id})
        ).json()
        assert junk["result"] == "invalid"

        other = await db.scalar(
            select(Screen.id).where(Screen.id != found.screen.id, Screen.name == "Screen 2")
        )
        assert other is not None
        other_show = await db.scalar(
            select(Show.id)
            .where(Show.screen_id == other, Show.starts_at > datetime.now(UTC))
            .limit(1)
        )
        wrong = (await usher.post("/checkin", json={"token": b, "show_id": str(other_show)})).json()
        assert wrong["result"] == "wrong_show"

        both = await asyncio.gather(
            usher.post("/checkin", json={"token": b, "show_id": show_id}),
            usher2.post("/checkin", json={"token": b, "show_id": show_id}),
        )
        assert sorted(r.json()["result"] for r in both) == ["used", "valid"]

    async with signed_in(db_app) as c:
        scanned = (await c.get(f"/tickets/{order['id']}")).json()["tickets"]
        assert all(t["checked_in_at"] for t in scanned)
    async with tab(db_app) as nandi:
        # Another business can't scan Orbit's show at all.
        await code_sign_in(db_app, nandi, "x@other.example", door="business", name="X",
                           business={"name": "Other Cinemas", "phone": "9845012345"})  # fmt: skip
        assert (
            await nandi.post("/checkin", json={"token": a, "show_id": show_id})
        ).status_code == 404
