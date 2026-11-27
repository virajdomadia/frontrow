"""L3: the Today board and blocked seats. A blocked seat can't be held, ordered or confirmed;
a block can't take a sold or held seat; a block and a sale of one seat never both win; the demo
owner can look (names masked) but not block a real show."""

import asyncio
import uuid
from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.models import BlockedSeat, Business, Cinema, Film, Order, Screen, Seat, Show, Ticket
from app.models.enums import BusinessStatus, FilmStatus, OrderStatus
from app.seed import seed
from app.services import boxoffice
from app.services import orders as order_svc
from app.services.payments import DemoGateway
from tests.helpers import OpenShow, demo, orbit_owner, signed_in, tab

pytestmark = [pytest.mark.db, pytest.mark.redis]


async def orbit_show(db: AsyncSession) -> OpenShow:
    """The emptiest upcoming public show at Orbit (the demo owner's real cinema)."""
    sold = select(func.count()).select_from(Ticket).where(Ticket.show_id == Show.id)
    show, screen = (
        (
            await db.execute(
                select(Show, Screen)
                .join(Screen, Screen.id == Show.screen_id)
                .join(Cinema, Cinema.id == Screen.cinema_id)
                .join(Business, Business.id == Cinema.business_id)
                .join(Film, Film.id == Show.film_id)
                .where(
                    Business.slug == "orbit-cinemas",
                    Business.status == BusinessStatus.VERIFIED,
                    Film.status == FilmStatus.NOW_SHOWING,
                    Show.starts_at > datetime.now(UTC),
                )
                .order_by(sold.scalar_subquery(), Show.starts_at)
                .limit(1)
            )
        )
        .one()
        ._tuple()
    )
    taken = set(await db.scalars(select(Ticket.seat_id).where(Ticket.show_id == show.id)))
    free: dict[str, list[str]] = {}
    for s in await db.scalars(
        select(Seat).where(Seat.screen_id == screen.id).order_by(Seat.y, Seat.x)
    ):
        if s.id not in taken:
            free.setdefault(s.tier_key, []).append(str(s.id))
    return OpenShow(show, screen, free)


async def test_blocked_seats_are_off_sale(
    db_engine: AsyncEngine, db: AsyncSession, db_app: FastAPI
) -> None:
    await seed(db_engine, now=datetime.now(UTC))
    found = await orbit_show(db)
    s1, s2, s3 = found.all_free[:3]
    url = f"/owner/shows/{found.show.id}/blocks"
    async with tab(db_app) as owner, signed_in(db_app, "asha") as customer:
        await orbit_owner(db_app, owner, db)
        res = await owner.post(url, json={"seat_ids": [s1, s2], "reason": "broken"})
        assert res.status_code == 200 and res.json()["seat_ids"] == [s1, s2]

        # Customers see them as unavailable and can't hold or order them.
        public = (await customer.get(f"/shows/{found.show.id}/seats")).json()
        assert set(public["blocked"]) == {s1, s2} and s1 not in public["sold"]
        hold = await customer.post(f"/shows/{found.show.id}/holds", json={"seat_ids": [s3, s1]})
        assert hold.status_code == 409 and hold.json()["error"]["details"] == {"taken": [s1]}

        # The owner's own map tells blocked from sold; the board counts them.
        mine = (await owner.get(f"/owner/shows/{found.show.id}/seats")).json()
        assert set(mine["blocked"]) == {s1, s2}
        board = (await owner.get("/owner/today")).json()
        assert "shows" in board and "recent" in board

        assert (await owner.request("DELETE", url, json={"seat_ids": [s1]})).status_code == 204
        hold = await customer.post(f"/shows/{found.show.id}/holds", json={"seat_ids": [s1]})
        assert hold.status_code == 200


async def test_block_refuses_sold_and_held_seats(
    db_engine: AsyncEngine, db: AsyncSession, db_app: FastAPI
) -> None:
    await seed(db_engine, now=datetime.now(UTC))
    found = await orbit_show(db)
    free = found.all_free
    sold = await db.scalar(select(Ticket.seat_id).where(Ticket.show_id == found.show.id))
    url = f"/owner/shows/{found.show.id}/blocks"
    async with tab(db_app) as owner, signed_in(db_app, "ravi") as customer:
        await orbit_owner(db_app, owner, db)
        if sold is not None:
            res = await owner.post(url, json={"seat_ids": [free[0], str(sold)], "reason": "staff"})
            assert res.status_code == 409 and res.json()["error"]["code"] == "seat_taken"
        # A customer holding a seat may be paying for it: hands off, and all or none.
        await customer.post(f"/shows/{found.show.id}/holds", json={"seat_ids": [free[1]]})
        res = await owner.post(url, json={"seat_ids": [free[0], free[1]], "reason": "guests"})
        assert res.status_code == 409 and res.json()["error"]["code"] == "seat_held"
        assert await db.scalar(select(func.count()).select_from(BlockedSeat)) == 0
        bad = await owner.post(url, json={"seat_ids": [free[0]], "reason": "vip"})
        assert bad.status_code == 422


async def test_a_block_after_the_hold_lapsed_refunds_the_payment(
    db_engine: AsyncEngine, db: AsyncSession, db_app: FastAPI
) -> None:
    """The customer's hold lapsed, the owner blocked the seat, then the payment lands: no
    ticket, the whole payment refunded."""
    await seed(db_engine, now=datetime.now(UTC))
    found = await orbit_show(db)
    seat = found.all_free[0]
    async with signed_in(db_app, "meera") as c:
        await c.post(f"/shows/{found.show.id}/holds", json={"seat_ids": [seat]})
        order = (
            await c.post("/orders", json={"show_id": str(found.show.id), "seat_ids": [seat]})
        ).json()
        db.add(BlockedSeat(show_id=found.show.id, seat_id=uuid.UUID(seat), reason="broken"))
        await db.commit()
        paid = (await c.post(f"/orders/{order['id']}/demo-pay")).json()
        assert paid["status"] == "refunded" and paid["refund_reason"] == "seat_sold"
    assert (
        await db.scalar(
            select(Ticket.id).where(
                Ticket.show_id == found.show.id, Ticket.seat_id == uuid.UUID(seat)
            )
        )
        is None
    )


async def test_block_and_sale_race_one_winner(
    db_engine: AsyncEngine, db: AsyncSession, db_app: FastAPI
) -> None:
    """A block and a payment for the same seat at the same moment, ten times over: each time
    exactly one of them has the seat."""
    await seed(db_engine, now=datetime.now(UTC))
    found = await orbit_show(db)
    orbit = await db.scalar(select(Business).where(Business.slug == "orbit-cinemas"))
    assert orbit is not None
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    for seat in found.all_free[:10]:
        async with signed_in(db_app, f"r{seat[:6]}") as c:
            await c.post(f"/shows/{found.show.id}/holds", json={"seat_ids": [seat]})
            made = await c.post("/orders", json={"show_id": str(found.show.id), "seat_ids": [seat]})
            order_id = uuid.UUID(made.json()["id"])

        async def pay(order_id: uuid.UUID = order_id) -> None:
            async with factory() as s:
                await order_svc.confirm(
                    s, None, DemoGateway(), order_id, payment_id="pay_x", now=datetime.now(UTC)
                )

        async def block(seat: str = seat) -> None:
            async with factory() as s:
                try:  # Redis is skipped (None): this is the database race alone
                    await boxoffice.block(
                        s, None, orbit, str(found.show.id), [seat], "staff",
                        holder=None, now=datetime.now(UTC),
                    )  # fmt: skip
                except Exception as e:  # the sale won: "That seat is sold"
                    assert getattr(e, "code", None) == "seat_taken", e

        await asyncio.gather(pay(), block())
        sid = uuid.UUID(seat)
        ticket = await db.scalar(
            select(Ticket.id).where(Ticket.show_id == found.show.id, Ticket.seat_id == sid)
        )
        blocked = await db.scalar(
            select(BlockedSeat.seat_id).where(
                BlockedSeat.show_id == found.show.id, BlockedSeat.seat_id == sid
            )
        )
        order = await db.get(Order, order_id, populate_existing=True)
        assert order is not None
        assert (ticket is None) != (blocked is None), seat
        assert (order.status == OrderStatus.PAID) == (ticket is not None)


async def test_demo_owner_can_look_but_not_block(
    db_engine: AsyncEngine, db: AsyncSession, db_app: FastAPI
) -> None:
    await seed(db_engine, now=datetime.now(UTC))
    found = await orbit_show(db)
    seat = found.all_free[-1]
    async with signed_in(db_app, "priya") as c:  # a real customer buys at Orbit today
        await c.post(f"/shows/{found.show.id}/holds", json={"seat_ids": [seat]})
        made = await c.post("/orders", json={"show_id": str(found.show.id), "seat_ids": [seat]})
        assert (await c.post(f"/orders/{made.json()['id']}/demo-pay")).json()["status"] == "paid"
    async with tab(db_app) as owner:
        await demo(owner, "owner")
        url = f"/owner/shows/{found.show.id}/blocks"
        for method in ("POST", "DELETE"):
            res = await owner.request(
                method, url, json={"seat_ids": found.all_free[:1], "reason": "staff"}
            )
            assert res.status_code == 403 and res.json()["error"]["code"] == "demo_read_only"
        assert (await owner.get(f"/owner/shows/{found.show.id}/seats")).status_code == 200
        board = (await owner.get("/owner/today")).json()
        names = [r["name"] for r in board["recent"]]
        assert "P." in names and not any("Priya" in n for n in names)
    assert await db.scalar(select(func.count()).select_from(BlockedSeat)) == 0


async def test_another_business_show_is_404(
    db_engine: AsyncEngine, db: AsyncSession, db_app: FastAPI
) -> None:
    await seed(db_engine, now=datetime.now(UTC))
    orbit = await orbit_show(db)
    other = await db.scalar(
        select(Show.id)
        .join(Screen, Screen.id == Show.screen_id)
        .join(Cinema, Cinema.id == Screen.cinema_id)
        .join(Business, Business.id == Cinema.business_id)
        .where(Business.slug != "orbit-cinemas")
        .limit(1)
    )
    async with tab(db_app) as owner:
        await orbit_owner(db_app, owner, db)
        for path in (f"/owner/shows/{other}/seats",):
            assert (await owner.get(path)).status_code == 404
        res = await owner.post(
            f"/owner/shows/{other}/blocks",
            json={"seat_ids": orbit.all_free[:1], "reason": "staff"},
        )
        assert res.status_code == 404
