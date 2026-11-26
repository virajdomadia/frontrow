"""B2: sign-in by email code at three doors (R1) — 04 §11 `test_otp` and `test_access_rules`.

- a new customer: email → code → name → signed in; the code works once
- wrong codes use up tries (five and it's gone); expired codes are refused
- one code a minute per email; the staff door answers the same for any email
- the business door registers a pending business; demo buttons for all three roles
- access: customer → owner/staff routes refused; demo staff can't decide
"""

import asyncio
from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.models import Business
from app.models.enums import BusinessStatus
from app.redis import redis_for
from app.seed import seed
from tests.helpers import code_sign_in, demo, open_show, tab

pytestmark = [pytest.mark.db, pytest.mark.redis]


async def test_new_customer_signs_up_with_a_code(db_app: FastAPI) -> None:
    outbox = db_app.state.mailer
    async with tab(db_app) as c:
        assert (await c.get("/auth/me")).status_code == 401
        sent = await c.post("/auth/code", json={"email": " Asha@Example.com ", "door": "customer"})
        assert sent.status_code == 204
        code = outbox.code_for("asha@example.com")
        assert "Frontrow" in outbox.sent[-1].subject

        # A new email has no name yet: 422 name_required, and the code still works after.
        body = {"email": "asha@example.com", "code": code, "door": "customer"}
        ask = await c.post("/auth/verify", json=body)
        assert ask.status_code == 422 and ask.json()["error"]["code"] == "name_required"
        me = await c.post("/auth/verify", json={**body, "name": "Asha"})
        assert me.status_code == 200, me.text
        assert me.json()["name"] == "Asha" and me.json()["businesses"] == []
        assert me.json()["is_staff"] is False and me.json()["is_demo"] is False
        assert (await c.get("/auth/me")).json()["email"] == "asha@example.com"

        # The code is spent.
        again = await c.post("/auth/verify", json={**body, "name": "Asha"})
        assert again.status_code == 401 and again.json()["error"]["code"] == "code_invalid"

        assert (await c.post("/auth/sign-out")).status_code == 204
        assert (await c.get("/auth/me")).status_code == 401


async def test_wrong_codes_run_out(db_app: FastAPI) -> None:
    async with tab(db_app) as c:
        await c.post("/auth/code", json={"email": "ravi@example.com"})
        good = db_app.state.mailer.code_for("ravi@example.com")
        bad = "000000" if good != "000000" else "111111"
        body = {"email": "ravi@example.com", "code": bad, "name": "Ravi"}
        lefts = []
        for _ in range(5):
            res = await c.post("/auth/verify", json=body)
            assert res.status_code == 401
            lefts.append((res.json()["error"].get("details") or {}).get("tries_left"))
        assert lefts == [4, 3, 2, 1, None]
        # Five wrong tries and even the right code is gone.
        late = await c.post("/auth/verify", json={**body, "code": good})
        assert late.status_code == 401


async def test_code_expiry_and_rate_limit(db_app: FastAPI) -> None:
    db_app.state.settings = db_app.state.settings.model_copy(update={"code_ttl_seconds": 1})
    async with tab(db_app) as c:
        assert (await c.post("/auth/code", json={"email": "meera@example.com"})).status_code == 204
        code = db_app.state.mailer.code_for("meera@example.com")
        again = await c.post("/auth/code", json={"email": "meera@example.com"})
        assert again.status_code == 429 and again.json()["error"]["code"] == "rate_limited"
        await asyncio.sleep(1.3)
        res = await c.post(
            "/auth/verify", json={"email": "meera@example.com", "code": code, "name": "Meera"}
        )
        assert res.status_code == 401 and "expired" in res.json()["error"]["message"]


async def test_demo_emails_and_no_smtp(db_app: FastAPI) -> None:
    async with tab(db_app) as c:
        demo_mail = await c.post("/auth/code", json={"email": "customer@frontrow.demo"})
        assert demo_mail.status_code == 422
        db_app.state.mailer = None  # a deployment with no SMTP configured
        off = await c.post("/auth/code", json={"email": "someone@example.com"})
        assert off.status_code == 503 and off.json()["error"]["code"] == "email_unavailable"


async def test_staff_door_says_nothing(db_engine: AsyncEngine, db_app: FastAPI) -> None:
    await seed(db_engine, now=datetime.now(UTC), staff="boss@frontrow.example")
    outbox = db_app.state.mailer
    async with tab(db_app) as c:
        stranger = await c.post("/auth/code", json={"email": "nobody@example.com", "door": "staff"})
        assert stranger.status_code == 204
        assert not any(m.to == "nobody@example.com" for m in outbox.sent)
        guess = await c.post(
            "/auth/verify",
            json={"email": "nobody@example.com", "code": "123456", "door": "staff"},
        )
        assert guess.status_code == 401

        me = await code_sign_in(db_app, c, "boss@frontrow.example", door="staff", name=None)
        assert me["is_staff"] is True and me["is_demo"] is False


async def test_business_door_registers_a_pending_business(
    db_app: FastAPI, db: AsyncSession
) -> None:
    async with tab(db_app) as c:
        await c.post("/auth/code", json={"email": "lata@sunrise.example", "door": "business"})
        code = db_app.state.mailer.code_for("lata@sunrise.example")
        body = {"email": "lata@sunrise.example", "code": code, "door": "business", "name": "Lata"}
        ask = await c.post("/auth/verify", json=body)
        assert ask.status_code == 422 and ask.json()["error"]["code"] == "business_required"
        me = await c.post(
            "/auth/verify",
            json={**body, "business": {"name": "Sunrise Talkies", "phone": "+91 80 1234 5678"}},
        )
        assert me.status_code == 200, me.text
        [biz] = me.json()["businesses"]
        assert biz["name"] == "Sunrise Talkies" and biz["status"] == "pending"
        console = await c.get("/owner/business")
        assert console.status_code == 200 and console.json()["status"] == "pending"
    business = await db.scalar(select(Business).where(Business.slug == "sunrise-talkies"))
    assert business is not None and business.status == BusinessStatus.PENDING


async def test_a_customer_can_add_a_business(db_app: FastAPI) -> None:
    async with tab(db_app) as c:
        await code_sign_in(db_app, c, "kiran@example.com", name="Kiran")
        assert (await c.get("/owner/cinemas")).status_code == 403
        made = await c.post(
            "/owner/business", json={"name": "Kiran Cinemas", "phone": "9845012345"}
        )
        assert made.status_code == 201 and made.json()["status"] == "pending"
        assert (await c.get("/owner/cinemas")).json() == []
        twice = await c.post("/owner/business", json={"name": "Again", "phone": "9845012345"})
        assert twice.status_code == 409


async def test_demo_buttons_and_access_rules(db_engine: AsyncEngine, db_app: FastAPI) -> None:
    await seed(db_engine, now=datetime.now(UTC))
    async with tab(db_app) as customer, tab(db_app) as owner, tab(db_app) as staff:
        me = await demo(customer, "customer")
        assert me["is_demo"] and not me["is_staff"] and me["businesses"] == []
        assert (await customer.get("/owner/cinemas")).status_code == 403
        assert (await customer.get("/staff/films")).status_code == 403
        assert (
            await customer.post("/checkin", json={"token": "x" * 20, "show_id": me["id"]})
        ).status_code == 403

        me = await demo(owner, "owner")
        assert [b["slug"] for b in me["businesses"]] == ["orbit-cinemas"]
        assert (await owner.get("/owner/cinemas")).status_code == 200
        assert (await owner.get("/staff/businesses")).status_code == 403

        me = await demo(staff, "staff")
        assert me["is_staff"] and me["is_demo"]
        assert (await staff.get("/staff/businesses?status=pending")).status_code == 200
        [pending] = (await staff.get("/staff/businesses?status=pending")).json()
        decide = await staff.patch(f"/staff/businesses/{pending['id']}", json={"action": "approve"})
        assert decide.status_code == 403 and decide.json()["error"]["code"] == "demo_read_only"


async def test_sign_in_keeps_the_visitors_holds(
    db_engine: AsyncEngine, db: AsyncSession, db_app: FastAPI
) -> None:
    """Seats held before signing in stay "mine" after (the session adopts `fr_sid`)."""
    await seed(db_engine, now=datetime.now(UTC))
    found = await open_show(db)
    async with tab(db_app) as c:
        seat = found.all_free[0]
        held = await c.post(f"/shows/{found.show.id}/holds", json={"seat_ids": [seat]})
        assert held.status_code == 200
        sid = c.cookies.get("fr_sid")
        await code_sign_in(db_app, c, "tara@example.com", name="Tara")
        assert c.cookies.get("fr_sid") == sid
        state = (await c.get(f"/shows/{found.show.id}/seats")).json()
        assert state["mine"] == [seat]


async def test_bearer_tokens(db_engine: AsyncEngine, db_app: FastAPI) -> None:
    async with tab(db_app) as web:
        await code_sign_in(db_app, web, "app@example.com", name="App User")
    # One code a minute per email: skip the wait by clearing the limiter key.
    redis = redis_for(db_app)
    assert redis is not None
    await redis.delete("rl:otp:m:app@example.com")
    async with tab(db_app) as phone:
        assert (
            await phone.post("/auth/code", json={"email": "app@example.com"})
        ).status_code == 204
        code = db_app.state.mailer.code_for("app@example.com")
        made = await phone.post("/auth/token", json={"email": "app@example.com", "code": code})
        assert made.status_code == 201
        token = made.json()["token"]
        headers = {"authorization": f"Bearer {token}"}
        assert (await phone.get("/auth/me", headers=headers)).json()["email"] == "app@example.com"
        assert (await phone.request("DELETE", "/auth/token", headers=headers)).status_code == 204
        assert (await phone.get("/auth/me", headers=headers)).status_code == 401
