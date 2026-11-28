"""L5: cancel a show. Every buyer is refunded in full exactly once, however often (or however
concurrently) cancel is called; a retry after a lost gateway answer adopts the refund Razorpay
already has; emails are recorded and sent after the money, and a failed or impossible send never
undoes a refund; the demo owner can't cancel a real show."""

import asyncio
import json
import uuid
from datetime import UTC, datetime

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.models import EmailOutbox, Order, Ticket, User
from app.models.enums import OrderStatus
from app.seed import seed
from app.services import boxoffice
from app.services.mail import Mail, MailError
from app.services.payments import DemoGateway, RazorpayGateway
from tests.helpers import Outbox, code_sign_in, demo, orbit_owner, signed_in, tab
from tests.test_boxoffice import orbit_show

pytestmark = [pytest.mark.db, pytest.mark.redis]

REASON = "Projector failure"


class CountingGateway(DemoGateway):
    def __init__(self) -> None:
        self.refunds: list[str] = []

    async def refund(self, payment_id: str, amount_paise: int) -> str | None:
        await asyncio.sleep(0.01)  # a real call takes time: let concurrent cancels overlap
        self.refunds.append(payment_id)
        return f"rfnd_{len(self.refunds)}"


class BrokenMailer:
    async def send(self, mail: Mail) -> None:
        raise MailError("SMTP refused: SMTPAuthenticationError")


async def buy(app: FastAPI, who: str, show_id: uuid.UUID, seats: list[str]) -> str:
    async with signed_in(app, who) as c:
        assert (await c.post(f"/shows/{show_id}/holds", json={"seat_ids": seats})).is_success
        order = (await c.post("/orders", json={"show_id": str(show_id), "seat_ids": seats})).json()
        assert (await c.post(f"/orders/{order['id']}/demo-pay")).json()["status"] == "paid"
        return order["id"]


async def setup(db_engine: AsyncEngine, db: AsyncSession, app: FastAPI, buyers: int = 3):
    await seed(db_engine, now=datetime.now(UTC))
    found = await orbit_show(db)
    gateway = CountingGateway()
    app.state.gateway = gateway
    free = found.all_free
    orders = [await buy(app, f"buyer{i}", found.show.id, [free[i]]) for i in range(buyers)]
    return found, gateway, orders


async def test_cancel_refunds_everyone_once_and_emails_them(
    db_engine: AsyncEngine, db: AsyncSession, db_app: FastAPI
) -> None:
    found, gateway, orders = await setup(db_engine, db, db_app)
    url = f"/owner/shows/{found.show.id}/cancel"
    async with tab(db_app) as owner:
        await orbit_owner(db_app, owner, db)
        counter = await owner.post(
            f"/owner/shows/{found.show.id}/counter-orders",
            json={"seat_ids": [found.all_free[10]], "idempotency_key": uuid.uuid4().hex},
        )
        token = counter.json()["tickets"][0]["qr_token"]
        res = await owner.post(url, json={"reason": REASON})
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["refunded"] >= 4 and body["remaining"] == 0 and body["refund_pending"] == 0
        # Our three online buyers; seeded bookers are skipped, the counter buyer gets cash back.
        assert body["emails"].get("sent") == 3

        # Again, and again at once: nothing refunded or emailed twice.
        await asyncio.gather(*(owner.post(url, json={"reason": REASON}) for _ in range(4)))
        paid = set(
            await db.scalars(
                select(Order.razorpay_payment_id).where(
                    Order.show_id == found.show.id, Order.razorpay_payment_id.is_not(None)
                )
            )
        )
        assert sorted(gateway.refunds) == sorted(p for p in paid if p)  # each refunded once
        for o in await db.scalars(select(Order).where(Order.id.in_(map(uuid.UUID, orders)))):
            assert o.status == OrderStatus.REFUNDED and o.refund_reason == "show_cancelled"
        sent: Outbox = db_app.state.mailer
        cancelled = [m for m in sent.sent if m.subject.startswith("Cancelled:")]
        assert len(cancelled) == 3 and REASON in cancelled[0].text

        # The show is gone for customers, its tickets don't open the door, no tickets remain.
        async with tab(db_app) as c:
            assert (await c.get(f"/shows/{found.show.id}/seats")).status_code == 410
        door = await owner.post("/checkin", json={"token": token, "show_id": str(found.show.id)})
        assert door.json()["result"] == "invalid"
        left = await db.scalar(
            select(func.count()).select_from(Ticket).where(Ticket.show_id == found.show.id)
        )
        assert left == 0


async def test_a_payment_after_the_cancel_is_refunded(
    db_engine: AsyncEngine, db: AsyncSession, db_app: FastAPI
) -> None:
    found, gateway, _ = await setup(db_engine, db, db_app, buyers=0)
    seat = found.all_free[0]
    async with signed_in(db_app, "late") as c, tab(db_app) as owner:
        await c.post(f"/shows/{found.show.id}/holds", json={"seat_ids": [seat]})
        made = await c.post("/orders", json={"show_id": str(found.show.id), "seat_ids": [seat]})
        await orbit_owner(db_app, owner, db)
        await owner.post(f"/owner/shows/{found.show.id}/cancel", json={"reason": REASON})
        paid = (await c.post(f"/orders/{made.json()['id']}/demo-pay")).json()
        assert paid["status"] == "refunded" and paid["refund_reason"] == "show_cancelled"
    assert len(gateway.refunds) == 1


async def test_email_trouble_never_undoes_a_refund(
    db_engine: AsyncEngine, db: AsyncSession, db_app: FastAPI
) -> None:
    found, gateway, orders = await setup(db_engine, db, db_app, buyers=2)
    async with tab(db_app) as owner:
        await orbit_owner(db_app, owner, db)
        db_app.state.mailer = BrokenMailer()
        res = await owner.post(f"/owner/shows/{found.show.id}/cancel", json={"reason": REASON})
    assert res.status_code == 200
    assert res.json()["emails"].get("failed") == 2 and res.json()["refund_pending"] == 0
    assert len(gateway.refunds) == 2
    errors = list(await db.scalars(select(EmailOutbox.error).where(EmailOutbox.status == "failed")))
    assert errors == ["SMTP refused: SMTPAuthenticationError"] * 2  # never the address


async def test_no_smtp_records_not_sent(
    db_engine: AsyncEngine, db: AsyncSession, db_app: FastAPI
) -> None:
    found, _, _ = await setup(db_engine, db, db_app, buyers=1)
    async with tab(db_app) as owner:
        await orbit_owner(db_app, owner, db)
        db_app.state.mailer = None  # a deployment with SMTP off
        res = await owner.post(f"/owner/shows/{found.show.id}/cancel", json={"reason": REASON})
    assert res.json()["emails"].get("not_sent") == 1 and res.json()["refund_pending"] == 0


async def test_big_show_finishes_over_several_calls(
    db_engine: AsyncEngine, db: AsyncSession, db_app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(boxoffice, "REFUND_BATCH", 2)
    found, gateway, _ = await setup(db_engine, db, db_app, buyers=5)
    url = f"/owner/shows/{found.show.id}/cancel"
    async with tab(db_app) as owner:
        await orbit_owner(db_app, owner, db)
        first = (await owner.post(url, json={"reason": REASON})).json()
        assert first["remaining"] > 0
        while (state := (await owner.post(url, json={"reason": REASON})).json())["remaining"]:
            pass
    assert state["refund_pending"] == 0 and state["emails"].get("sent") == 5
    assert len(gateway.refunds) == len(set(gateway.refunds)) == 5


async def test_demo_owner_cannot_cancel_and_demo_staff_sees_masked_mail(
    db_engine: AsyncEngine, db: AsyncSession, db_app: FastAPI
) -> None:
    found, gateway, _ = await setup(db_engine, db, db_app, buyers=1)
    async with tab(db_app) as owner:
        await demo(owner, "owner")
        res = await owner.post(f"/owner/shows/{found.show.id}/cancel", json={"reason": REASON})
        assert res.status_code == 403 and res.json()["error"]["code"] == "demo_read_only"
    assert gateway.refunds == []
    async with tab(db_app) as owner:  # a real owner cancels; the email lands in the outbox
        await orbit_owner(db_app, owner, db)
        await owner.post(f"/owner/shows/{found.show.id}/cancel", json={"reason": REASON})
    async with tab(db_app) as staff:
        await demo(staff, "staff")
        mail = [m for m in (await staff.get("/staff/outbox")).json() if m["status"] == "sent"]
        assert len(mail) == 1 and mail[0]["to"] == "b***@example.com"
        assert REASON in mail[0]["body"]
    async with tab(db_app) as staff:
        boss = User(email="ops@frontrow.example", name="Ops", is_staff=True)
        db.add(boss)
        await db.commit()
        await code_sign_in(db_app, staff, boss.email, door="staff", name=None)
        mail = [m for m in (await staff.get("/staff/outbox")).json() if m["status"] == "sent"]
        assert mail[0]["to"] == "buyer0@example.com"


async def test_razorpay_refund_adopts_a_refund_it_already_made() -> None:
    """The refund went through at Razorpay but our call timed out: the retry finds it and
    doesn't refund again."""
    refunds: list[dict] = []
    lose_answer = True

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal lose_answer
        if request.method == "GET" and request.url.path.endswith("/refunds"):
            return httpx.Response(200, json={"items": refunds})
        if request.url.path.endswith("/refund"):
            refunds.append({"id": f"rfnd_{len(refunds) + 1}", "status": "processed",
                            "amount": json.loads(request.content)["amount"]})  # fmt: skip
            if lose_answer:
                lose_answer = False
                raise httpx.ReadTimeout("lost answer")
            return httpx.Response(200, json=refunds[-1])
        return httpx.Response(404)

    gw = RazorpayGateway("rzp_test_x", "secret", transport=httpx.MockTransport(handler))
    assert await gw.refund("pay_1", 49000) is None  # timed out: "refund in progress"
    assert await gw.refund("pay_1", 49000) == "rfnd_1"  # adopted, not refunded again
    assert len(refunds) == 1
