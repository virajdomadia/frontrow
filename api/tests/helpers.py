"""Test helpers: browser tabs, a recording mailer, demo / email-code sign-in, an open show."""

from __future__ import annotations

import re
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Business, Cinema, Screen, Seat, Show, Ticket
from app.models.enums import BusinessStatus, FilmStatus
from app.services.mail import Mail


class Outbox:
    """A mailer that keeps what it was asked to send."""

    def __init__(self) -> None:
        self.sent: list[Mail] = []

    async def send(self, mail: Mail) -> None:
        self.sent.append(mail)

    def code_for(self, email: str) -> str:
        for mail in reversed(self.sent):
            if mail.to == email:
                found = re.search(r"\b(\d{6})\b", mail.subject)
                if found:
                    return found.group(1)
        raise AssertionError(f"no code was sent to {email}")


def tab(app: FastAPI) -> AsyncClient:
    """A browser tab with its own cookie jar."""
    return AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test"
    )


async def demo(c: AsyncClient, as_: str = "customer") -> dict[str, Any]:
    res = await c.post("/auth/demo", json={"as": as_})
    assert res.status_code == 200, res.text
    return res.json()


async def code_sign_in(
    app: FastAPI,
    c: AsyncClient,
    email: str,
    *,
    door: str = "customer",
    name: str | None = "Test Person",
    business: dict[str, str] | None = None,
) -> dict[str, Any]:
    sent = await c.post("/auth/code", json={"email": email, "door": door})
    assert sent.status_code == 204, sent.text
    code = app.state.mailer.code_for(email)
    body: dict[str, Any] = {"email": email, "code": code, "door": door, "name": name}
    if business:
        body["business"] = business
    res = await c.post("/auth/verify", json=body)
    assert res.status_code == 200, res.text
    return res.json()


@asynccontextmanager
async def signed_in(app: FastAPI, who: str = "customer") -> AsyncIterator[AsyncClient]:
    """The demo customer, or a fresh customer account named `who` (email code)."""
    async with tab(app) as c:
        if who == "customer":
            await demo(c)
        else:
            await code_sign_in(app, c, f"{who}@example.com", name=who.title())
        yield c


@dataclass
class OpenShow:
    show: Show
    screen: Screen
    free: dict[str, list[str]]  # tier → free seat ids, front to back

    @property
    def all_free(self) -> list[str]:
        return [s for seats in self.free.values() for s in seats]


async def open_show(db: AsyncSession, template: str = "grid", *, tiers: int = 3) -> OpenShow:
    """The emptiest upcoming public show on a screen of `template` with `tiers` tiers or more."""
    sold_count = (
        select(func.count()).select_from(Ticket).where(Ticket.show_id == Show.id)
    ).scalar_subquery()
    from app.models import Film

    rows = (
        await db.execute(
            select(Show, Screen)
            .join(Screen, Screen.id == Show.screen_id)
            .join(Cinema, Cinema.id == Screen.cinema_id)
            .join(Business, Business.id == Cinema.business_id)
            .join(Film, Film.id == Show.film_id)
            .where(
                Screen.template == template,
                Business.status == BusinessStatus.VERIFIED,
                Film.status == FilmStatus.NOW_SHOWING,
                Show.starts_at > datetime.now(UTC),
            )
            .order_by(sold_count, Show.starts_at)
        )
    ).tuples()
    for show, screen in rows:
        if len(screen.tiers) < tiers:
            continue
        sold = set(await db.scalars(select(Ticket.seat_id).where(Ticket.show_id == show.id)))
        free: dict[str, list[str]] = {}
        for s in await db.scalars(
            select(Seat).where(Seat.screen_id == screen.id).order_by(Seat.y, Seat.x)
        ):
            if s.id not in sold:
                free.setdefault(s.tier_key, []).append(str(s.id))
        return OpenShow(show, screen, free)
    raise AssertionError("no open show")


def uid() -> str:
    return uuid.uuid4().hex[:8]
