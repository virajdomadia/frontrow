"""L4: counter sales. Paid in cash at the box office, on the same live map and under the same
guards as online: no seat sold twice (online vs counter, counter vs counter), a retried or
double-tapped sale is one sale (idempotency key), and the demo owner can't sell real seats."""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.models import BlockedSeat, Business, BusinessMember, Order, Ticket, User
from app.models.enums import OrderChannel, OrderStatus
from app.seed import seed
from app.services import orders as order_svc
from app.services.payments import DemoGateway
from tests.helpers import code_sign_in, demo, orbit_owner, signed_in, tab
from tests.test_boxoffice import orbit_show

pytestmark = [pytest.mark.db, pytest.mark.redis]


def sale(seats: list[str], key: str | None = None) -> dict:
    return {"seat_ids": seats, "idempotency_key": key or uuid.uuid4().hex}


async def tickets_for(db: AsyncSession, show_id: uuid.UUID, seat: str) -> int:
    return (
        await db.scalar(
            select(func.count())
            .select_from(Ticket)
            .where(Ticket.show_id == show_id, Ticket.seat_id == uuid.UUID(seat))
        )
        or 0
    )


async def test_counter_sale_issues_tickets(
    db_engine: AsyncEngine, db: AsyncSession, db_app: FastAPI
) -> None:
    await seed(db_engine, now=datetime.now(UTC))
    found = await orbit_show(db)
    s1, s2 = found.all_free[:2]
    url = f"/owner/shows/{found.show.id}/counter-orders"
    async with tab(db_app) as owner, signed_in(db_app, "kiran") as customer:
        await orbit_owner(db_app, owner, db)
        res = await owner.post(url, json=sale([s1, s2]))
        assert res.status_code == 201, res.text
        body = res.json()
        assert body["order"]["status"] == "paid" and body["order"]["fee_paise"] == 0
        assert body["order"]["payment_method"] == "Cash at the counter"
        assert [t["seat_id"] for t in body["tickets"]] == [s1, s2]
        token = body["tickets"][0]["qr_token"]  # scanned at the door like any ticket
        door = await owner.post("/checkin", json={"token": token, "show_id": str(found.show.id)})
        assert door.status_code == 200 and door.json()["result"] == "valid", door.text

        public = (await customer.get(f"/shows/{found.show.id}/seats")).json()
        assert {s1, s2} <= set(public["sold"])
        hold = await customer.post(f"/shows/{found.show.id}/holds", json={"seat_ids": [s1]})
        assert hold.status_code == 409

        board = (await owner.get("/owner/today")).json()
        assert any(r["channel"] == "counter" and r["seats"] == 2 for r in board["recent"])
        # Counter sales are the cinema's, not the cashier's own tickets.
        assert (await owner.get("/my/tickets")).json()["upcoming"] == []


async def test_counter_sale_is_idempotent(
    db_engine: AsyncEngine, db: AsyncSession, db_app: FastAPI
) -> None:
    await seed(db_engine, now=datetime.now(UTC))
    found = await orbit_show(db)
    s1, s2 = found.all_free[:2]
    url = f"/owner/shows/{found.show.id}/counter-orders"
    async with tab(db_app) as owner:
        await orbit_owner(db_app, owner, db)
        key = uuid.uuid4().hex
        first = await owner.post(url, json=sale([s1], key))
        again = await owner.post(url, json=sale([s1], key))  # the retry after a timeout
        assert first.status_code == 201 and again.status_code == 201
        assert first.json()["order"]["id"] == again.json()["order"]["id"]
        assert await tickets_for(db, found.show.id, s1) == 1
        reused = await owner.post(url, json=sale([s2], key))  # same key, other seats: a bug
        assert (
            reused.status_code == 409 and reused.json()["error"]["code"] == "idempotency_conflict"
        )

        # Five taps of the same sale at once: one order.
        key = uuid.uuid4().hex
        codes = await asyncio.gather(*(owner.post(url, json=sale([s2], key)) for _ in range(5)))
        assert {c.status_code for c in codes} == {201}
        assert len({c.json()["order"]["id"] for c in codes}) == 1
        assert await tickets_for(db, found.show.id, s2) == 1


async def test_counter_never_double_sells(
    db_engine: AsyncEngine, db: AsyncSession, db_app: FastAPI
) -> None:
    """Ten cashiers sell the same seat at once (different keys): exactly one sale."""
    await seed(db_engine, now=datetime.now(UTC))
    found = await orbit_show(db)
    seat = found.all_free[0]
    url = f"/owner/shows/{found.show.id}/counter-orders"
    async with tab(db_app) as owner:
        await orbit_owner(db_app, owner, db)
        codes = [
            r.status_code
            for r in await asyncio.gather(*(owner.post(url, json=sale([seat])) for _ in range(10)))
        ]
    assert sorted(codes) == [201] + [409] * 9
    assert await tickets_for(db, found.show.id, seat) == 1


async def test_counter_vs_online_one_winner(
    db_engine: AsyncEngine, db: AsyncSession, db_app: FastAPI
) -> None:
    """An online payment landing late and a counter sale of the same seat at the same moment:
    one ticket; the online buyer is refunded if the counter won."""
    await seed(db_engine, now=datetime.now(UTC))
    found = await orbit_show(db)
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with tab(db_app) as owner:
        await orbit_owner(db_app, owner, db)
        for seat in found.all_free[:8]:
            async with signed_in(db_app, f"o{seat[:6]}") as c:
                await c.post(f"/shows/{found.show.id}/holds", json={"seat_ids": [seat]})
                made = await c.post(
                    "/orders", json={"show_id": str(found.show.id), "seat_ids": [seat]}
                )
                order_id = uuid.UUID(made.json()["id"])
                await c.request(
                    "DELETE", f"/shows/{found.show.id}/holds", json={"seat_ids": [seat]}
                )
            await db.execute(
                update(Order).where(Order.id == order_id)
                .values(created_at=datetime.now(UTC) - timedelta(minutes=20))
            )  # fmt: skip
            await db.commit()

            async def pay(order_id: uuid.UUID = order_id) -> None:
                async with factory() as s:
                    await order_svc.confirm(
                        s, None, DemoGateway(), order_id, payment_id="pay_y", now=datetime.now(UTC)
                    )

            async def counter(seat: str = seat) -> int:
                return (
                    await owner.post(
                        f"/owner/shows/{found.show.id}/counter-orders", json=sale([seat])
                    )
                ).status_code

            _, code = await asyncio.gather(pay(), counter())
            online = await db.get(Order, order_id, populate_existing=True)
            assert online is not None
            assert await tickets_for(db, found.show.id, seat) == 1
            assert (code == 201) == (online.status == OrderStatus.REFUNDED), (code, online.status)


async def test_counter_refuses_unavailable_seats(
    db_engine: AsyncEngine, db: AsyncSession, db_app: FastAPI
) -> None:
    await seed(db_engine, now=datetime.now(UTC))
    found = await orbit_show(db)
    free = found.all_free
    url = f"/owner/shows/{found.show.id}/counter-orders"
    db.add(BlockedSeat(show_id=found.show.id, seat_id=uuid.UUID(free[0]), reason="broken"))
    await db.commit()
    async with tab(db_app) as owner, signed_in(db_app, "dev") as customer:
        await orbit_owner(db_app, owner, db)
        blocked = await owner.post(url, json=sale([free[0]]))
        assert blocked.status_code == 409 and blocked.json()["error"]["code"] == "seat_taken"
        await customer.post(f"/shows/{found.show.id}/holds", json={"seat_ids": [free[1]]})
        held = await owner.post(url, json=sale([free[1], free[2]]))
        assert held.status_code == 409 and held.json()["error"]["code"] == "seat_held"
        assert await tickets_for(db, found.show.id, free[2]) == 0  # all or none
        too_many = await owner.post(url, json=sale(free[3:14]))
        assert too_many.status_code == 422


async def test_demo_owner_cannot_sell(
    db_engine: AsyncEngine, db: AsyncSession, db_app: FastAPI
) -> None:
    await seed(db_engine, now=datetime.now(UTC))
    found = await orbit_show(db)
    async with tab(db_app) as owner:
        await demo(owner, "owner")
        res = await owner.post(
            f"/owner/shows/{found.show.id}/counter-orders", json=sale(found.all_free[:1])
        )
        assert res.status_code == 403 and res.json()["error"]["code"] == "demo_read_only"
    count = await db.scalar(
        select(func.count()).select_from(Order).where(Order.channel == OrderChannel.COUNTER)
    )
    assert count == 0


async def test_other_business_show_is_404(
    db_engine: AsyncEngine, db: AsyncSession, db_app: FastAPI
) -> None:
    await seed(db_engine, now=datetime.now(UTC))
    found = await orbit_show(db)
    async with tab(db_app) as c:
        # A real owner of another business.
        other = await db.scalar(select(Business).where(Business.slug != "orbit-cinemas"))
        assert other is not None
        u = User(email="boss@elsewhere.example", name="Boss")
        db.add(u)
        await db.flush()
        db.add(BusinessMember(business_id=other.id, user_id=u.id, role="owner"))
        await db.commit()
        await code_sign_in(db_app, c, u.email, door="business", name=None)
        res = await c.post(
            f"/owner/shows/{found.show.id}/counter-orders", json=sale(found.all_free[:1])
        )
        assert res.status_code == 404


async def test_another_cashier_can_replay_a_sale(
    db_engine: AsyncEngine, db: AsyncSession, db_app: FastAPI
) -> None:
    """The till retries on a second cashier's login (same business): the first sale comes back."""
    await seed(db_engine, now=datetime.now(UTC))
    found = await orbit_show(db)
    seat = found.all_free[0]
    url = f"/owner/shows/{found.show.id}/counter-orders"
    key = uuid.uuid4().hex
    async with tab(db_app) as first, tab(db_app) as second:
        await orbit_owner(db_app, first, db)
        sold = await first.post(url, json=sale([seat], key))
        orbit = await db.scalar(select(Business).where(Business.slug == "orbit-cinemas"))
        assert orbit is not None
        u = User(email="till2@orbit.example", name="Till Two")
        db.add(u)
        await db.flush()
        db.add(BusinessMember(business_id=orbit.id, user_id=u.id, role="owner"))
        await db.commit()
        await code_sign_in(db_app, second, u.email, door="business", name=None)
        again = await second.post(url, json=sale([seat], key))
        assert again.status_code == 201
        assert again.json()["order"]["id"] == sold.json()["order"]["id"]
