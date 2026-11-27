"""B6/B7: orders, payment confirmation, refunds and QR tickets (04 §11).

- `test_order_total`            server-side total = Σ tier price + ₹30 × seats
- `test_webhook_signature_and_replay`
- `test_confirm_unique`         two paid orders for one seat → one ticket, one refund
- `test_paid_after_expiry_*`    both branches: seats still free → sold; sold meanwhile → refund
"""

import asyncio
import json
import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from pydantic import SecretStr
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.models import Order, OrderSeat, Screen, Show, ShowPrice, Ticket, User
from app.models.enums import OrderStatus
from app.seed import seed
from app.services import orders as svc
from app.services import tickets
from app.services.payments import DemoGateway, RazorpayGateway, hmac_hex
from tests.conftest import TEST_HOLD_TTL
from tests.helpers import open_show, signed_in, tab

pytestmark = [pytest.mark.db, pytest.mark.redis]

KEY_SECRET = "rzp-test-key-secret"
WEBHOOK_SECRET = "rzp-test-webhook-secret"


class RazorpayStub:
    """Razorpay's REST API in-process: order ids out, refunds recorded."""

    def __init__(self) -> None:
        self.refunds: list[tuple[str, int]] = []
        self.orders: list[tuple[str, int]] = []  # (id, amount), newest last
        self.payment_status = "captured"
        self.amount_delta = 0

    def handler(self, request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/orders":
            made = (f"order_{uuid.uuid4().hex[:14]}", json.loads(request.content)["amount"])
            self.orders.append(made)
            return httpx.Response(200, json={"id": made[0]})
        if request.method == "GET" and request.url.path.startswith("/v1/payments/"):
            order_id, amount = self.orders[-1]  # the payment is for the latest order
            return httpx.Response(200, json={
                "id": request.url.path.split("/")[3], "order_id": order_id,
                "status": self.payment_status, "amount": amount - self.amount_delta,
                "currency": "INR",
            })  # fmt: skip
        if request.url.path.endswith("/refund"):
            payment = request.url.path.split("/")[3]
            self.refunds.append((payment, json.loads(request.content)["amount"]))
            return httpx.Response(200, json={"id": f"rfnd_{uuid.uuid4().hex[:10]}"})
        return httpx.Response(404)


def use_razorpay(app: FastAPI) -> RazorpayStub:
    stub = RazorpayStub()
    app.state.gateway = RazorpayGateway(
        "rzp_test_frontrow", KEY_SECRET, transport=httpx.MockTransport(stub.handler)
    )
    app.state.settings = app.state.settings.model_copy(
        update={"razorpay_webhook_secret": SecretStr(WEBHOOK_SECRET)}
    )
    return stub


async def grid_showtime(db: AsyncSession) -> tuple[Show, Screen, dict[str, list[str]]]:
    found = await open_show(db)
    return found.show, found.screen, found.free


async def hold_and_order(c: AsyncClient, showtime: Show, seats: list[str]) -> dict:
    held = await c.post(f"/shows/{showtime.id}/holds", json={"seat_ids": seats})
    assert held.status_code == 200, held.text
    res = await c.post("/orders", json={"show_id": str(showtime.id), "seat_ids": seats})
    assert res.status_code == 201, res.text
    return res.json()


def webhook(order: dict, payment_id: str, event_id: str) -> tuple[bytes, dict[str, str]]:
    body = json.dumps(
        {
            "event": "payment.captured",
            "payload": {
                "payment": {
                    "entity": {
                        "id": payment_id,
                        "order_id": order["razorpay_order_id"],
                        "amount": order["total_paise"],
                        "currency": "INR",
                    }
                }
            },
        }
    ).encode()
    return body, {
        "x-razorpay-signature": hmac_hex(WEBHOOK_SECRET, body),
        "x-razorpay-event-id": event_id,
        "content-type": "application/json",
    }


async def test_order_total(db_engine: AsyncEngine, db: AsyncSession, db_app: FastAPI) -> None:
    await seed(db_engine, now=datetime.now(UTC))
    showtime, _, free = await grid_showtime(db)
    seats = [free["classic"][0], free["recliner"][0]]
    prices = {
        t.tier_key: t.price_paise
        for t in await db.scalars(select(ShowPrice).where(ShowPrice.show_id == showtime.id))
    }
    async with signed_in(db_app) as c:
        order = await hold_and_order(c, showtime, seats)
        assert order["status"] == "pending" and order["gateway"] == "demo"
        assert order["subtotal_paise"] == prices["classic"] + prices["recliner"]
        assert order["fee_paise"] == 2 * 3000
        assert order["total_paise"] == prices["classic"] + prices["recliner"] + 6000
        assert order["hold_expires_at"] and len(order["seats"]) == 2
        assert {s["tier_label"] for s in order["seats"]} == {"Classic", "Recliner"}

        # Proceed twice → the same pending order, not a second one.
        again = await c.post("/orders", json={"show_id": str(showtime.id), "seat_ids": seats[::-1]})
        assert again.json()["id"] == order["id"]


async def test_order_needs_a_live_hold(
    db_engine: AsyncEngine, db: AsyncSession, db_app: FastAPI
) -> None:
    await seed(db_engine, now=datetime.now(UTC))
    showtime, _, free = await grid_showtime(db)
    body = {"show_id": str(showtime.id), "seat_ids": [free["prime"][0]]}
    async with tab(db_app) as anon:
        assert (await anon.post("/orders", json=body)).status_code == 401
    async with signed_in(db_app) as c:
        res = await c.post("/orders", json=body)
        assert res.status_code == 409 and res.json()["error"]["code"] == "hold_missing"


async def test_demo_pay_tickets_and_privacy(
    db_engine: AsyncEngine, db: AsyncSession, db_app: FastAPI
) -> None:
    await seed(db_engine, now=datetime.now(UTC))
    showtime, _, free = await grid_showtime(db)
    seats = free["prime"][:2]
    async with signed_in(db_app) as c:
        order = await hold_and_order(c, showtime, seats)
        paid = await c.post(f"/orders/{order['id']}/demo-pay")
        assert paid.status_code == 200 and paid.json()["status"] == "paid"
        # Replaying the payment is a no-op.
        assert (await c.post(f"/orders/{order['id']}/demo-pay")).json()["status"] == "paid"

        state = (await c.get(f"/shows/{showtime.id}/seats")).json()
        assert set(seats) <= set(state["sold"]) and state["mine"] == []

        bundle = await c.get(f"/tickets/{order['id']}")
        assert bundle.status_code == 200
        issued = bundle.json()["tickets"]
        assert len(issued) == 2
        for t in issued:
            verified = tickets.verify(db_app.state.settings, t["qr_token"], now=datetime.now(UTC))
            assert verified is not None and str(verified.ticket_id) == t["id"]
            assert verified.show_id == showtime.id
        token = issued[0]["qr_token"]
        # Change one character in the middle of the MAC (the last one carries padding bits).
        forged = token[:-6] + ("B" if token[-6] != "B" else "C") + token[-5:]
        assert tickets.verify(db_app.state.settings, forged, now=datetime.now(UTC)) is None

        mine = (await c.get("/my/tickets")).json()
        assert order["id"] in [g["order_id"] for g in mine["upcoming"]]

    async with signed_in(db_app, "stranger") as other:
        assert (await other.get(f"/tickets/{order['id']}")).status_code == 404
        assert (await other.get(f"/orders/{order['id']}")).status_code == 404


async def test_verify_signature(db_engine: AsyncEngine, db: AsyncSession, db_app: FastAPI) -> None:
    await seed(db_engine, now=datetime.now(UTC))
    use_razorpay(db_app)
    showtime, _, free = await grid_showtime(db)
    async with signed_in(db_app) as c:
        order = await hold_and_order(c, showtime, [free["classic"][3]])
        assert order["gateway"] == "razorpay" and order["key_id"] == "rzp_test_frontrow"
        assert order["razorpay_order_id"].startswith("order_")
        url = f"/orders/{order['id']}/verify"
        forged = await c.post(url, json={"razorpay_payment_id": "pay_1", "razorpay_signature": "0"})
        assert forged.status_code == 400
        sig = hmac_hex(KEY_SECRET, f"{order['razorpay_order_id']}|pay_1".encode())
        ok = await c.post(url, json={"razorpay_payment_id": "pay_1", "razorpay_signature": sig})
        assert ok.status_code == 200 and ok.json()["status"] == "paid"
        assert (await c.post(f"/orders/{order['id']}/demo-pay")).status_code == 409


async def test_webhook_signature_and_replay(
    db_engine: AsyncEngine, db: AsyncSession, db_app: FastAPI
) -> None:
    await seed(db_engine, now=datetime.now(UTC))
    use_razorpay(db_app)
    showtime, _, free = await grid_showtime(db)
    async with signed_in(db_app) as c:
        order = await hold_and_order(c, showtime, free["prime"][4:6])

    body, headers = webhook(order, "pay_hook_1", "evt_1")
    async with tab(db_app) as razorpay:
        forged = await razorpay.post(
            "/webhooks/razorpay", content=body, headers={**headers, "x-razorpay-signature": "bad"}
        )
        assert forged.status_code == 400
        assert (await db.get(Order, uuid.UUID(order["id"]))).status == OrderStatus.PENDING  # type: ignore[union-attr]

        first = await razorpay.post("/webhooks/razorpay", content=body, headers=headers)
        assert first.status_code == 200 and first.json() == {"status": "confirmed"}
        replay = await razorpay.post("/webhooks/razorpay", content=body, headers=headers)
        assert replay.status_code == 200 and replay.json() == {"status": "duplicate"}

    count = await db.scalar(
        select(func.count()).select_from(Ticket).where(Ticket.order_id == uuid.UUID(order["id"]))
    )
    assert count == 2


async def test_confirm_unique(db_engine: AsyncEngine, db: AsyncSession, db_app: FastAPI) -> None:
    """Two paid orders for the same seat, confirmed at the same moment: one gets the ticket,
    the other is refunded — the UNIQUE (show_id, seat_id) guard, not Redis, decides."""
    await seed(db_engine, now=datetime.now(UTC))
    showtime, _, free = await grid_showtime(db)
    seat = uuid.UUID(free["classic"][5])
    users = list(await db.scalars(select(User).order_by(User.email).limit(2)))
    order_ids = []
    for u in users:
        o = Order(
            user_id=u.id, sid=f"sid-{u.id}", show_id=showtime.id, status=OrderStatus.PENDING,
            subtotal_paise=22000, fee_paise=3000, total_paise=25000, razorpay_order_id=None,
        )  # fmt: skip
        db.add(o)
        await db.flush()
        db.add(OrderSeat(order_id=o.id, seat_id=seat, tier_key="classic", price_paise=22000))
        order_ids.append(o.id)
    await db.commit()

    gateway = DemoGateway()
    factory = async_sessionmaker(db_engine, expire_on_commit=False)

    async def pay(order_id: uuid.UUID) -> OrderStatus:
        async with factory() as s:
            done = await svc.confirm(
                s, None, gateway, order_id, payment_id=f"pay_{order_id.hex[:6]}",
                now=datetime.now(UTC),
            )  # fmt: skip
            return done.status

    statuses = await asyncio.gather(*(pay(o) for o in order_ids))
    assert sorted(statuses) == [OrderStatus.PAID, OrderStatus.REFUNDED]
    tickets_for_seat = await db.scalar(
        select(func.count())
        .select_from(Ticket)
        .where(Ticket.seat_id == seat, Ticket.show_id == showtime.id)
    )
    assert tickets_for_seat == 1
    refunded = await db.scalar(select(Order).where(Order.status == OrderStatus.REFUNDED))
    assert refunded is not None and refunded.refund_reason == "seat_sold" and refunded.refund_id


async def test_paid_after_expiry_seats_still_free(
    db_engine: AsyncEngine, db: AsyncSession, db_app: FastAPI
) -> None:
    await seed(db_engine, now=datetime.now(UTC))
    stub = use_razorpay(db_app)
    showtime, _, free = await grid_showtime(db)
    async with signed_in(db_app) as c:
        order = await hold_and_order(c, showtime, [free["classic"][8]])
    await asyncio.sleep(TEST_HOLD_TTL + 0.3)  # the hold lapses while the customer pays

    body, headers = webhook(order, "pay_late_1", "evt_late_1")
    async with tab(db_app) as razorpay:
        res = await razorpay.post("/webhooks/razorpay", content=body, headers=headers)
    assert res.json() == {"status": "confirmed"}
    assert (await db.get(Order, uuid.UUID(order["id"]))).status == OrderStatus.PAID  # type: ignore[union-attr]
    assert stub.refunds == []


async def test_paid_after_expiry_seat_sold_meanwhile(
    db_engine: AsyncEngine, db: AsyncSession, db_app: FastAPI
) -> None:
    await seed(db_engine, now=datetime.now(UTC))
    stub = use_razorpay(db_app)
    showtime, _, free = await grid_showtime(db)
    seat = free["classic"][9]
    async with signed_in(db_app) as slow:
        late = await hold_and_order(slow, showtime, [seat])
    await asyncio.sleep(TEST_HOLD_TTL + 0.3)

    # Someone else takes the lapsed seat and pays first.
    async with signed_in(db_app, "quick") as quick:
        first = await hold_and_order(quick, showtime, [seat])
        sig = hmac_hex(KEY_SECRET, f"{first['razorpay_order_id']}|pay_quick".encode())
        ok = await quick.post(
            f"/orders/{first['id']}/verify",
            json={"razorpay_payment_id": "pay_quick", "razorpay_signature": sig},
        )
        assert ok.json()["status"] == "paid"

    body, headers = webhook(late, "pay_slow", "evt_slow")
    async with tab(db_app) as razorpay:
        assert (await razorpay.post("/webhooks/razorpay", content=body, headers=headers)).is_success
    async with tab(db_app) as again:
        await again.post("/auth/demo", json={"as": "customer"})
        seen = (await again.get(f"/orders/{late['id']}")).json()
    assert seen["status"] == "refunded" and seen["refund_reason"] == "seat_sold"
    assert stub.refunds == [("pay_slow", late["total_paise"])]


async def test_pending_orders_expire_on_read(
    db_engine: AsyncEngine, db: AsyncSession, db_app: FastAPI
) -> None:
    await seed(db_engine, now=datetime.now(UTC))
    showtime, _, free = await grid_showtime(db)
    async with signed_in(db_app) as c:
        order = await hold_and_order(c, showtime, [free["prime"][9]])
        await db.execute(
            update(Order)
            .where(Order.id == uuid.UUID(order["id"]))
            .values(created_at=datetime.now(UTC) - timedelta(minutes=16))
        )
        await db.commit()
        assert (await c.get(f"/orders/{order['id']}")).json()["status"] == "expired"
