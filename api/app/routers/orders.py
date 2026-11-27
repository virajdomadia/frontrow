"""Orders, payments and tickets (06 §C): `/orders`, `/orders/{id}/verify`, `/orders/{id}/demo-pay`,
`/webhooks/razorpay`, `/tickets/{order_id}`, `/my/tickets`. Everything here is per-user and
`no-store`."""

import hashlib
import json
import logging
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, Response
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.db import get_session
from app.errors import ApiError
from app.models import Order, User, WebhookEvent
from app.redis import optional_redis, require_redis
from app.schemas.orders import CreateOrder, MyTickets, TicketBundle, VerifyPayment
from app.schemas.orders import Order as OrderOut
from app.services import orders as svc
from app.services.auth import Auth, holder_of, is_demo, require_auth
from app.services.mail import mailer_for, ticket_mail
from app.services.payments import Gateway, gateway_for, webhook_signature_ok
from app.services.schedules import BOOKER_DOMAIN, IST

log = logging.getLogger(__name__)

router = APIRouter(tags=["orders"])

Db = Annotated[AsyncSession, Depends(get_session)]
Signed = Annotated[Auth, Depends(require_auth)]
OptRedis = Annotated[Redis | None, Depends(optional_redis)]


def gateway(request: Request) -> Gateway:
    return gateway_for(request.app)


Pay = Annotated[Gateway, Depends(gateway)]


def _no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


def email_tickets(request: Request, db: AsyncSession) -> svc.OnPaid:
    """After a sale: email the M-ticket link (R7). Never for demo or seeded accounts, never
    blocking the sale — `confirm` logs a failure and moves on."""

    async def send(order: Order) -> None:
        mailer = mailer_for(request.app)
        user = await db.get(User, order.user_id) if order.user_id else None
        if mailer is None or user is None or is_demo(user) or user.email.endswith(BOOKER_DOMAIN):
            return
        show, screen = await svc.show_out(db, order.show_id)
        seats = await svc.seats_out(db, order, screen)
        settings: Settings = request.app.state.settings
        local = show.starts_at.astimezone(IST)
        await mailer.send(
            ticket_mail(
                user.email,
                title=show.film.title,
                when=local.strftime("%a %d %b, %I:%M %p").replace(" 0", " "),
                cinema=f"{show.cinema.name} · {show.screen_name}",
                seats=", ".join(s.label for s in seats),
                url=f"{settings.web_url.rstrip('/')}/tickets/{order.id}",
            )
        )

    return send


@router.post("/orders", response_model=OrderOut, status_code=201)
async def create_order(
    body: CreateOrder,
    request: Request,
    response: Response,
    db: Db,
    auth: Signed,
    pay: Pay,
    redis: Annotated[Redis, Depends(require_redis)],
) -> OrderOut:
    """Check the holds, price the seats server-side, open a gateway order. 409 `hold_missing`
    when a hold lapsed; pressing Proceed twice returns the same pending order."""
    _no_store(response)
    holder = holder_of(request, response, auth, create=False)
    if holder is None:
        raise ApiError(
            "hold_missing",
            "Pick your seats on the map first",
            status=409,
            details={"missing": body.seat_ids},
        )
    order = await svc.create(
        db,
        redis,
        pay,
        user=auth.user,
        holder=holder,
        show_id=body.show_id,
        seat_ids=body.seat_ids,
        now=datetime.now(UTC),
    )
    return await svc.view(db, order, pay, user=auth.user, redis=redis)


@router.get("/orders/{order_id}", response_model=OrderOut)
async def get_order(
    order_id: str, response: Response, db: Db, auth: Signed, pay: Pay, redis: OptRedis
) -> OrderOut:
    _no_store(response)
    order = await svc.owned_order(db, order_id, auth.user, datetime.now(UTC))
    return await svc.view(db, order, pay, user=auth.user, redis=redis)


@router.post("/orders/{order_id}/verify", response_model=OrderOut)
async def verify_payment(
    order_id: str,
    body: VerifyPayment,
    request: Request,
    response: Response,
    db: Db,
    auth: Signed,
    pay: Pay,
    redis: OptRedis,
) -> OrderOut:
    """The Checkout handler's fast path: a valid signature confirms at once (the webhook,
    arriving later, finds the order paid and does nothing)."""
    _no_store(response)
    now = datetime.now(UTC)
    order = await svc.owned_order(db, order_id, auth.user, now)
    if not order.razorpay_order_id or not pay.signature_ok(
        order.razorpay_order_id, body.razorpay_payment_id, body.razorpay_signature
    ):
        raise ApiError("bad_signature", "The payment signature didn't verify", status=400)
    # A signature proves authorisation, not capture: check the payment itself.
    payment = await pay.payment(body.razorpay_payment_id)
    if not _matches(payment, order):
        raise ApiError("payment_mismatch", "That payment isn't for this order", status=400)
    if payment.get("status") != "captured":
        raise ApiError(
            "payment_pending",
            "Your payment is still being confirmed. Your tickets will appear here once it is.",
            status=409,
        )
    order = await svc.confirm(
        db, redis, pay, order.id, payment_id=body.razorpay_payment_id, now=now,
        on_paid=email_tickets(request, db),
    )  # fmt: skip
    return await svc.view(db, order, pay, user=auth.user, redis=redis)


@router.post("/orders/{order_id}/demo-pay", response_model=OrderOut)
async def demo_pay(
    order_id: str,
    request: Request,
    response: Response,
    db: Db,
    auth: Signed,
    pay: Pay,
    redis: OptRedis,
) -> OrderOut:
    """Test-mode payment when no Razorpay keys are configured: confirms through the same path
    as a webhook. 409 when real Razorpay is configured."""
    _no_store(response)
    if pay.mode != "demo":
        raise ApiError("conflict", "Pay with Razorpay Checkout")
    now = datetime.now(UTC)
    order = await svc.owned_order(db, order_id, auth.user, now)
    order = await svc.confirm(
        db, redis, pay, order.id, payment_id=svc.demo_payment_id(), now=now,
        on_paid=email_tickets(request, db),
    )  # fmt: skip
    return await svc.view(db, order, pay, user=auth.user, redis=redis)


def _matches(payment: dict[str, Any], order: Order) -> bool:
    """The gateway's payment is for this order, in full, in rupees."""
    return (
        payment.get("order_id") == order.razorpay_order_id
        and payment.get("amount") == order.total_paise
        and payment.get("currency") == "INR"
    )


def _method(payment: dict[str, Any]) -> str:
    kind = str(payment.get("method") or "").upper()
    return f"Razorpay · {kind}" if kind else "Razorpay"


@router.post("/webhooks/razorpay", tags=["webhooks"])
async def razorpay_webhook(request: Request, db: Db, pay: Pay, redis: OptRedis) -> dict[str, str]:
    """HMAC-checked; deduplicated by Razorpay's event id (a replay is a no-op); always 200
    once the signature is good, so Razorpay stops retrying."""
    settings: Settings = request.app.state.settings
    if settings.razorpay_webhook_secret is None:
        raise ApiError("unavailable", "Webhooks are not configured")
    body = await request.body()
    if not webhook_signature_ok(settings, body, request.headers.get("x-razorpay-signature")):
        raise ApiError("bad_signature", "Invalid webhook signature", status=400)
    event_id = request.headers.get("x-razorpay-event-id") or hashlib.sha256(body).hexdigest()
    try:
        event: dict[str, Any] = json.loads(body)
    except ValueError as e:
        raise ApiError("validation", "Webhook body is not JSON") from e

    fresh = await db.scalar(
        pg_insert(WebhookEvent)
        .values(id=event_id)
        .on_conflict_do_nothing()
        .returning(WebhookEvent.id)
    )
    if fresh is None:
        await db.rollback()
        return {"status": "duplicate"}

    kind = event.get("event")
    payment = (event.get("payload") or {}).get("payment", {}).get("entity", {})
    rzp_order = payment.get("order_id")
    order = None
    if rzp_order:
        order = await db.scalar(select(Order).where(Order.razorpay_order_id == rzp_order))
    if kind == "payment.captured" and order is not None and not _matches(payment, order):
        log.error("webhook %s: payment doesn't match order %s; not confirmed", event_id, order.id)
        await db.commit()
        return {"status": "ignored"}
    if kind == "payment.captured" and order is not None and payment.get("id"):
        # The event row commits in the same transaction as the confirm: if confirming fails,
        # neither sticks and Razorpay's retry gets a clean second go.
        await svc.confirm(
            db, redis, pay, order.id, payment_id=str(payment["id"]), now=datetime.now(UTC),
            method=_method(payment), on_paid=email_tickets(request, db),
        )  # fmt: skip
        return {"status": "confirmed"}
    if kind == "payment.failed" and rzp_order:
        await svc.mark_failed(db, rzp_order)
        return {"status": "failed"}
    await db.commit()
    log.info("webhook %s ignored (%s)", event_id, kind)
    return {"status": "ignored"}


@router.get("/tickets/{order_id}", response_model=TicketBundle)
async def get_tickets(
    order_id: str, request: Request, response: Response, db: Db, auth: Signed, pay: Pay
) -> TicketBundle:
    """One QR per seat. Someone else's order → 404."""
    _no_store(response)
    return await svc.ticket_bundle(
        db, request.app.state.settings, pay, order_id, user=auth.user, now=datetime.now(UTC)
    )


@router.get("/my/tickets", response_model=MyTickets)
async def my_tickets(response: Response, db: Db, auth: Signed) -> MyTickets:
    _no_store(response)
    return await svc.my_tickets(db, auth.user, now=datetime.now(UTC))
