"""F4: sign-up / sign-in / sign-out / me / demo, bearer tokens, and the role guard."""

from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.models import Session
from app.seed import seed

pytestmark = pytest.mark.db


def tab(app: FastAPI) -> AsyncClient:
    return AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test"
    )


async def test_sign_up_in_out(db_app: FastAPI, db: AsyncSession) -> None:
    async with tab(db_app) as c:
        assert (await c.get("/auth/me")).status_code == 401
        up = await c.post(
            "/auth/sign-up",
            json={"email": " Asha@Example.com ", "password": "seats-please", "name": "Asha"},
        )
        assert up.status_code == 201, up.text
        assert up.json()["email"] == "asha@example.com" and up.json()["role"] == "customer"
        cookie = up.headers["set-cookie"]
        assert "fr_session=" in cookie and "HttpOnly" in cookie and "SameSite=lax" in cookie
        assert (await c.get("/auth/me")).json()["name"] == "Asha"

        # The stored session id is a keyed hash, never the cookie value itself.
        token = c.cookies["fr_session"]
        assert await db.scalar(select(Session).where(Session.id == token)) is None

        dupe = await c.post(
            "/auth/sign-up", json={"email": "asha@example.com", "password": "x" * 8, "name": "A"}
        )
        assert dupe.status_code == 409 and dupe.json()["error"]["code"] == "email_taken"

        assert (await c.post("/auth/sign-out")).status_code == 204
        assert (await c.get("/auth/me")).status_code == 401

        bad = await c.post("/auth/sign-in", json={"email": "asha@example.com", "password": "nope"})
        assert bad.status_code == 401
        good = await c.post(
            "/auth/sign-in", json={"email": "ASHA@example.com", "password": "seats-please"}
        )
        assert good.status_code == 200 and (await c.get("/auth/me")).status_code == 200

        short = await c.post(
            "/auth/sign-up", json={"email": "b@example.com", "password": "short", "name": "B"}
        )
        assert short.status_code == 422


async def test_sign_in_adopts_the_visitor_sid(db_app: FastAPI, db: AsyncSession) -> None:
    """Seats held before signing in stay yours: the session records the fr_sid cookie."""
    async with tab(db_app) as c:
        c.cookies.set("fr_sid", "visitor-123")
        await c.post(
            "/auth/sign-up", json={"email": "v@example.com", "password": "password1", "name": "V"}
        )
        session = await db.scalar(select(Session))
        assert session is not None and session.sid == "visitor-123"


async def test_demo_and_bearer_tokens(db_engine: AsyncEngine, db_app: FastAPI) -> None:
    await seed(db_engine, now=datetime.now(UTC))
    async with tab(db_app) as c:
        demo = await c.post("/auth/demo", json={"as": "organiser"})
        assert demo.status_code == 200 and demo.json()["role"] == "organiser"

    async with tab(db_app) as app_client:
        res = await app_client.post(
            "/auth/token", json={"email": "customer@frontrow.demo", "password": "frontrow-demo"}
        )
        assert res.status_code == 201
        token = res.json()["token"]
        bearer = {"Authorization": f"Bearer {token}"}
        me = await app_client.get("/auth/me", headers=bearer)
        assert me.status_code == 200 and me.json()["email"] == "customer@frontrow.demo"
        assert (
            await app_client.request("DELETE", "/auth/token", headers=bearer)
        ).status_code == 204
        assert (await app_client.get("/auth/me", headers=bearer)).status_code == 401


async def test_organiser_routes_403_for_customers(db_engine: AsyncEngine, db_app: FastAPI) -> None:
    await seed(db_engine, now=datetime.now(UTC))
    async with tab(db_app) as c:
        assert (await c.get("/organiser/venues")).status_code == 401
        await c.post("/auth/demo", json={"as": "customer"})
        res = await c.get("/organiser/venues")
        assert res.status_code == 403 and res.json()["error"]["code"] == "forbidden"
