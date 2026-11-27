"""Review 2026-11-27 fixes: demo accounts can't touch real data or read real PII, holds are
bounded per network, the staff door gives nothing away, payments are checked before tickets."""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from starlette.requests import Request

from app.main import create_app
from app.models import Business, Cinema, Film, Order, OrderSeat, Screen, Show, User
from app.models.enums import FilmStatus, OrderStatus
from app.redis import redis_for
from app.seed import seed
from app.services import auth as auth_svc
from app.services import orders as order_svc
from app.services.payments import DemoGateway
from tests.helpers import code_sign_in, demo, open_show, signed_in, tab
from tests.settings import make_settings

pytestmark = [pytest.mark.db, pytest.mark.redis]


async def book(app: FastAPI, who: str, show_id: uuid.UUID, seats: list[str]) -> dict:
    async with signed_in(app, who) as c:
        assert (await c.post(f"/shows/{show_id}/holds", json={"seat_ids": seats})).is_success
        order = (await c.post("/orders", json={"show_id": str(show_id), "seat_ids": seats})).json()
        paid = (await c.post(f"/orders/{order['id']}/demo-pay")).json()
        assert paid["status"] == "paid"
        paid["tickets"] = (await c.get(f"/tickets/{order['id']}")).json()["tickets"]
        return paid


# --- C1: the demo owner ---------------------------------------------------------------------------


async def test_demo_owner_is_read_only(db_engine: AsyncEngine, db_app: FastAPI) -> None:
    """Every owner write (and the door) answers 403 `demo_read_only` for the demo owner."""
    await seed(db_engine, now=datetime.now(UTC))
    writes = [
        (method.upper(), path)
        for path, ops in db_app.openapi()["paths"].items()
        if path.startswith(("/owner", "/checkin")) and path != "/owner/screens/preview"
        for method in ops
        if method != "get" and (method, path) != ("post", "/owner/business")  # tested below
    ]
    assert len(writes) >= 7
    async with tab(db_app) as owner:
        await demo(owner, "owner")
        for method, path in writes:
            url = path.replace("{cinema_id}", str(uuid.uuid4()))
            res = await owner.request(method, url, json={})
            assert res.status_code == 403, (method, path, res.text)
            assert res.json()["error"]["code"] == "demo_read_only"
        # The live preview is a pure calculation, so it stays open.
        preview = await owner.post(
            "/owner/screens/preview", json={"knobs": {"template": "stalls_balcony"}}
        )
        assert preview.status_code == 200
    async with tab(db_app) as customer:
        await demo(customer, "customer")
        made = await customer.post(
            "/owner/business", json={"name": "Demo Co", "phone": "9845012345"}
        )
        assert made.status_code == 403 and made.json()["error"]["code"] == "demo_read_only"


async def test_demo_owner_sees_customers_masked(
    db_engine: AsyncEngine, db: AsyncSession, db_app: FastAPI
) -> None:
    await seed(db_engine, now=datetime.now(UTC))
    found = await open_show(db)
    await book(db_app, "zoya", found.show.id, found.free["prime"][:2])
    async with tab(db_app) as owner:
        await demo(owner, "owner")
        res = await owner.get(f"/owner/shows/{found.show.id}/bookings")
        assert res.status_code == 200
        assert "zoya@example.com" not in res.text and "Zoya" not in res.text
        assert any(b["email"] == "z***@example.com" for b in res.json()["bookings"])
        csv = await owner.get(f"/owner/shows/{found.show.id}/bookings", params={"format": "csv"})
        assert "zoya@example.com" not in csv.text and "Zoya" not in csv.text


async def test_demo_customer_bookings_reset(
    db_engine: AsyncEngine, db: AsyncSession, db_app: FastAPI
) -> None:
    """What a visitor books as the demo customer is undone on a later demo sign-in, so the seats
    go back on sale; the seeded bookings and real customers' tickets stay."""
    await seed(db_engine, now=datetime.now(UTC))
    found = await open_show(db)
    visitor = await book(db_app, "customer", found.show.id, found.free["classic"][:2])
    real = await book(db_app, "zoya", found.show.id, found.free["classic"][2:3])
    demo_id = await db.scalar(select(User.id).where(User.email == "customer@frontrow.demo"))
    kept_before = set(
        await db.scalars(
            select(Order.id).where(Order.user_id == demo_id, Order.razorpay_order_id.is_(None))
        )
    )
    async with tab(db_app) as c:
        await demo(c)  # a fresh booking is left alone
    assert await db.get(Order, uuid.UUID(visitor["id"])) is not None
    await db.execute(
        update(Order)
        .where(Order.id == uuid.UUID(visitor["id"]))
        .values(created_at=datetime.now(UTC) - timedelta(minutes=20))
    )
    await db.commit()
    async with tab(db_app) as c:
        await demo(c)
        seats = (await c.get(f"/shows/{found.show.id}/seats")).json()
    db.expire_all()
    assert await db.get(Order, uuid.UUID(visitor["id"])) is None
    assert not set(found.free["classic"][:2]) & set(seats["sold"])
    assert await db.get(Order, uuid.UUID(real["id"])) is not None
    kept_after = set(await db.scalars(select(Order.id).where(Order.user_id == demo_id)))
    assert kept_before <= kept_after


# --- H1: demo staff -------------------------------------------------------------------------------


async def test_demo_staff_sees_owner_contacts_masked(
    db_engine: AsyncEngine, db_app: FastAPI
) -> None:
    await seed(db_engine, now=datetime.now(UTC), staff="boss@frontrow.example")
    async with tab(db_app) as owner:
        await code_sign_in(
            db_app, owner, "lata@sunrise.example", door="business", name="Lata",
            business={"name": "Sunrise Talkies", "phone": "+91 80 1234 5678"},
        )  # fmt: skip
        await owner.post("/owner/film-requests", json={"title": "Some Film", "note": "call 98450"})
    async with tab(db_app) as staff:
        await demo(staff, "staff")
        biz = await staff.get("/staff/businesses")
        assert "lata@sunrise.example" not in biz.text and "1234 5678" not in biz.text
        [sunrise] = [b for b in biz.json() if b["name"] == "Sunrise Talkies"]
        assert sunrise["owners"][0]["email"] == "l***@sunrise.example"
        assert sunrise["phone"].endswith("5678") and "1234" not in sunrise["phone"]
        reqs = (await staff.get("/staff/film-requests")).json()
        assert [r["note"] for r in reqs if r["title"] == "Some Film"] == [None]
    async with tab(db_app) as real:
        await code_sign_in(db_app, real, "boss@frontrow.example", door="staff", name=None)
        assert "lata@sunrise.example" in (await real.get("/staff/businesses")).text


# --- H2: hold flood -------------------------------------------------------------------------------


async def test_hold_flood_is_capped_per_network(
    db_engine: AsyncEngine, db: AsyncSession, db_app: FastAPI
) -> None:
    """Rotating the `fr_sid` cookie doesn't buy more seats: one network holds at most 20 seats
    of a show (two tabs of 10). Another network still can."""
    await seed(db_engine, now=datetime.now(UTC))
    found = await open_show(db)
    free = found.all_free
    held = 0
    for i in range(6):
        async with tab(db_app) as c:  # a fresh cookie jar each time
            res = await c.post(
                f"/shows/{found.show.id}/holds", json={"seat_ids": free[i * 10 : i * 10 + 10]}
            )
            held += 10 if res.status_code == 200 else 0
            if res.status_code != 200:
                assert res.status_code == 429, res.text
    assert held == 20
    async with tab(db_app) as other:
        res = await other.post(
            f"/shows/{found.show.id}/holds",
            json={"seat_ids": free[100:101]},
            headers={"x-real-ip": "203.0.113.9"},
        )
        assert res.status_code == 200, res.text


async def test_hold_cap_is_atomic(
    db_engine: AsyncEngine, db: AsyncSession, db_app: FastAPI
) -> None:
    """Concurrent requests from one holder can't add up past 10 seats."""
    await seed(db_engine, now=datetime.now(UTC))
    found = await open_show(db)
    free = found.all_free
    async with tab(db_app) as c:
        await c.post(f"/shows/{found.show.id}/holds", json={"seat_ids": free[:1]})  # the cookie
        await asyncio.gather(
            *(
                c.post(
                    f"/shows/{found.show.id}/holds", json={"seat_ids": free[1 + i * 5 : 6 + i * 5]}
                )
                for i in range(3)
            )
        )
        mine = (await c.get(f"/shows/{found.show.id}/seats")).json()["mine"]
    assert len(mine) <= 10


# --- M1 / M2 / L3: sign-in codes ------------------------------------------------------------------


async def test_staff_door_answers_alike(db_engine: AsyncEngine, db_app: FastAPI) -> None:
    await seed(db_engine, now=datetime.now(UTC), staff="boss@frontrow.example")
    bodies = []
    for email in ("nobody@example.com", "boss@frontrow.example"):
        async with tab(db_app) as c:
            assert (
                await c.post("/auth/code", json={"email": email, "door": "staff"})
            ).status_code == 204
            res = await c.post(
                "/auth/verify", json={"email": email, "code": "000000", "door": "staff"}
            )
            bodies.append(
                (
                    res.status_code,
                    res.json()["error"]["message"],
                    res.json()["error"].get("details"),
                )
            )
    assert bodies[0] == bodies[1]


def _request(headers: dict[str, str], host: str = "10.0.0.1") -> Request:
    return Request(
        {
            "type": "http",
            "headers": [(k.encode(), v.encode()) for k, v in headers.items()],
            "client": (host, 1234),
        }
    )


def test_client_ip_is_not_spoofable() -> None:
    settings = make_settings(proxy_secret="s3cret")
    spoof = _request({"x-forwarded-for": "1.2.3.4"})
    assert auth_svc.client_ip(spoof, settings) == "10.0.0.1"
    assert auth_svc.client_ip(_request({"x-real-ip": "198.51.100.7"}), settings) == "198.51.100.7"
    via_web = {"x-frontrow-client-ip": "203.0.113.5", "x-frontrow-proxy": "s3cret"}
    assert auth_svc.client_ip(_request(via_web), settings) == "203.0.113.5"
    forged = {**via_web, "x-frontrow-proxy": "guess"}
    assert auth_svc.client_ip(_request(forged), settings) == "10.0.0.1"
    assert auth_svc.client_ip(_request(via_web), make_settings()) == "10.0.0.1"


async def test_code_limit_ignores_plus_tags(db_app: FastAPI) -> None:
    async with tab(db_app) as c:
        assert (await c.post("/auth/code", json={"email": "a.b+1@gmail.com"})).status_code == 204
        again = await c.post("/auth/code", json={"email": "ab+2@gmail.com"})
        assert again.status_code == 429


async def test_code_tries_are_atomic(app: FastAPI) -> None:
    redis = redis_for(app)
    assert redis is not None
    settings = app.state.settings
    email = "race@example.com"
    await redis.hset(auth_svc._code_key(email), mapping={"h": "x", "t": 0})

    async def guess() -> str:
        try:
            await auth_svc.check_code(redis, settings, email, "000000", consume=False)
        except Exception as e:  # noqa: BLE001
            return str(getattr(e, "message", e))
        return "ok"

    out = await asyncio.gather(*(guess() for _ in range(12)))
    assert "ok" not in out
    assert sum("left" in m for m in out) == 4
    assert not await redis.exists(auth_svc._code_key(email))  # not resurrected by late guesses


# --- L1 / L2 --------------------------------------------------------------------------------------


def test_deployment_refuses_dev_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VERCEL", "1")
    with pytest.raises(RuntimeError):
        create_app(settings=make_settings())
    create_app(settings=make_settings(session_secret="a", ticket_secret="b", proxy_secret="c"))


async def test_cross_site_posts_are_refused(db_app: FastAPI) -> None:
    async with tab(db_app) as c:
        evil = await c.post("/auth/sign-out", headers={"origin": "https://evil.virajdomadia.com"})
        assert evil.status_code == 403
        ok = await c.post("/auth/sign-out", headers={"origin": "http://localhost:3000"})
        assert ok.status_code == 204
        assert (await c.post("/auth/sign-out")).status_code == 204  # apps send no Origin


# --- L4 / L5 --------------------------------------------------------------------------------------


async def test_shows_outside_the_catalogue_cant_be_held(
    db_engine: AsyncEngine, db: AsyncSession, db_app: FastAPI
) -> None:
    await seed(db_engine, now=datetime.now(UTC))
    found = await open_show(db)
    await db.execute(
        update(Film).where(Film.id == found.show.film_id).values(status=FilmStatus.COMING_SOON)
    )
    await db.commit()
    async with tab(db_app) as c:
        res = await c.post(f"/shows/{found.show.id}/holds", json={"seat_ids": found.all_free[:1]})
        assert res.status_code == 404


async def test_concurrent_orders_are_one(
    db_engine: AsyncEngine, db: AsyncSession, db_app: FastAPI
) -> None:
    await seed(db_engine, now=datetime.now(UTC))
    found = await open_show(db)
    seats = found.free["classic"][:2]
    async with signed_in(db_app, "dup") as c:
        await c.post(f"/shows/{found.show.id}/holds", json={"seat_ids": seats})
        body = {"show_id": str(found.show.id), "seat_ids": seats}
        both = await asyncio.gather(c.post("/orders", json=body), c.post("/orders", json=body))
    assert {r.status_code for r in both} == {201}
    assert both[0].json()["id"] == both[1].json()["id"]


# --- L7 -------------------------------------------------------------------------------------------


async def test_door_hides_other_cinemas_customers(
    db_engine: AsyncEngine, db: AsyncSession, db_app: FastAPI
) -> None:
    await seed(db_engine, now=datetime.now(UTC))
    found = await open_show(db)
    paid = await book(db_app, "zoya", found.show.id, found.free["classic"][:1])
    token = paid["tickets"][0]["qr_token"]
    # A show of another business: Nandi's.
    nandi_show = await db.scalar(
        select(Show.id)
        .join(Screen, Screen.id == Show.screen_id)
        .join(Cinema, Cinema.id == Screen.cinema_id)
        .join(Business, Business.id == Cinema.business_id)
        .where(Business.slug != "orbit-cinemas", Show.starts_at > datetime.now(UTC))
        .limit(1)
    )
    nandi_biz = await db.scalar(
        select(Business)
        .join(Cinema, Cinema.business_id == Business.id)
        .join(Screen, Screen.cinema_id == Cinema.id)
        .join(Show, Show.screen_id == Screen.id)
        .where(Show.id == nandi_show)
    )
    assert nandi_biz is not None
    from app.models import BusinessMember

    usher_user = User(email="usher@other.example", name="Usher")
    db.add(usher_user)
    await db.flush()
    db.add(BusinessMember(business_id=nandi_biz.id, user_id=usher_user.id, role="owner"))
    await db.commit()
    async with tab(db_app) as usher:
        await code_sign_in(db_app, usher, usher_user.email, door="business", name=None)
        res = (
            await usher.post("/checkin", json={"token": token, "show_id": str(nandi_show)})
        ).json()
    assert res["result"] == "wrong_show"
    assert res["name"] is None and res["seat"] is None and "Zoya" not in str(res)


# --- M3: a refund that fails ----------------------------------------------------------------------


class FlakyRefunds(DemoGateway):
    def __init__(self) -> None:
        self.fail = True

    async def refund(self, payment_id: str, amount_paise: int) -> str | None:
        return None if self.fail else "rfnd_retried"


async def test_failed_refund_is_pending_then_retried(
    db_engine: AsyncEngine, db: AsyncSession, db_app: FastAPI
) -> None:
    await seed(db_engine, now=datetime.now(UTC))
    found = await open_show(db)
    seat = uuid.UUID(found.free["classic"][5])
    users = list(await db.scalars(select(User).order_by(User.email).limit(2)))
    ids = []
    for u in users:
        o = Order(
            user_id=u.id, sid=f"sid-{u.id}", show_id=found.show.id, status=OrderStatus.PENDING,
            subtotal_paise=22000, fee_paise=3000, total_paise=25000,
        )  # fmt: skip
        db.add(o)
        await db.flush()
        db.add(OrderSeat(order_id=o.id, seat_id=seat, tier_key="classic", price_paise=22000))
        ids.append(o.id)
    await db.commit()
    gateway = FlakyRefunds()
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    for oid in ids:
        async with factory() as s:
            await order_svc.confirm(
                s, None, gateway, oid, payment_id=f"pay_{oid.hex[:6]}", now=datetime.now(UTC)
            )
    async with factory() as s:
        loser = await s.get(Order, ids[1])
        assert (
            loser is not None and loser.status == OrderStatus.REFUNDED and loser.refund_id is None
        )
        user = await s.get(User, loser.user_id)
        assert user is not None
        out = await order_svc.view(s, loser, gateway, user=user, redis=None)
        assert out.refund_pending is True
        gateway.fail = False
        out = await order_svc.view(s, loser, gateway, user=user, redis=None)
        assert out.refund_pending is False and loser.refund_id == "rfnd_retried"


# --- L8: Checkout's fast path checks the payment itself -------------------------------------------


async def test_verify_needs_a_captured_payment(
    db_engine: AsyncEngine, db: AsyncSession, db_app: FastAPI
) -> None:
    from tests.test_orders import KEY_SECRET, hmac_hex, hold_and_order, use_razorpay

    await seed(db_engine, now=datetime.now(UTC))
    stub = use_razorpay(db_app)
    found = await open_show(db)
    async with signed_in(db_app) as c:
        order = await hold_and_order(c, found.show, [found.free["classic"][3]])
        sig = hmac_hex(KEY_SECRET, f"{order['razorpay_order_id']}|pay_1".encode())
        stub.payment_status = "authorized"
        res = await c.post(
            f"/orders/{order['id']}/verify",
            json={"razorpay_payment_id": "pay_1", "razorpay_signature": sig},
        )
        assert res.status_code == 409 and res.json()["error"]["code"] == "payment_pending"
        stub.payment_status = "captured"
        stub.amount_delta = 100  # paid less than the order
        res = await c.post(
            f"/orders/{order['id']}/verify",
            json={"razorpay_payment_id": "pay_1", "razorpay_signature": sig},
        )
        assert res.status_code == 400
        stub.amount_delta = 0
        ok = await c.post(
            f"/orders/{order['id']}/verify",
            json={"razorpay_payment_id": "pay_1", "razorpay_signature": sig},
        )
        assert ok.status_code == 200 and ok.json()["status"] == "paid"


async def test_webhook_checks_the_amount(
    db_engine: AsyncEngine, db: AsyncSession, db_app: FastAPI
) -> None:
    from tests.test_orders import hold_and_order, use_razorpay, webhook

    await seed(db_engine, now=datetime.now(UTC))
    use_razorpay(db_app)
    found = await open_show(db)
    async with signed_in(db_app) as c:
        order = await hold_and_order(c, found.show, [found.free["classic"][4]])
    body, headers = webhook({**order, "total_paise": order["total_paise"] - 1}, "pay_x", "evt_x")
    async with tab(db_app) as razorpay:
        res = await razorpay.post("/webhooks/razorpay", content=body, headers=headers)
    assert res.json() == {"status": "ignored"}
    assert (await db.get(Order, uuid.UUID(order["id"]))).status == OrderStatus.PENDING  # type: ignore[union-attr]
