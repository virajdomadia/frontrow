"""Payment gateways (04 §6): Razorpay (test mode) or a built-in demo gateway.

`RazorpayGateway` talks to Razorpay's REST API with httpx (orders, refunds) and checks the two
HMACs Razorpay uses: the Checkout handler's `order_id|payment_id` signature (key secret) and the
webhook body signature (webhook secret).

`DemoGateway` is what runs when no Razorpay keys are configured — a reviewer can still finish a
booking end to end. It never claims a real payment: the web says "test payment, no money
moves", and the order is confirmed through exactly the same `confirm` path as a webhook.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
from typing import Any, Literal, Protocol

import httpx
from fastapi import FastAPI

from app.config import Settings
from app.errors import ApiError

log = logging.getLogger(__name__)

RAZORPAY_API = "https://api.razorpay.com/v1"


class Gateway(Protocol):
    mode: Literal["razorpay", "demo"]
    key_id: str | None

    async def create_order(self, amount_paise: int, receipt: str) -> str: ...

    def signature_ok(self, order_id: str, payment_id: str, signature: str) -> bool: ...

    async def refund(self, payment_id: str, amount_paise: int) -> str | None: ...

    async def payment(self, payment_id: str) -> dict[str, Any]: ...


def hmac_hex(secret: str, message: bytes) -> str:
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


class RazorpayGateway:
    mode: Literal["razorpay", "demo"] = "razorpay"

    def __init__(
        self, key_id: str, key_secret: str, transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        self.key_id: str | None = key_id
        self._secret = key_secret
        self._transport = transport

    def _client(self) -> httpx.AsyncClient:
        assert self.key_id is not None
        return httpx.AsyncClient(
            base_url=RAZORPAY_API,
            auth=(self.key_id, self._secret),
            timeout=15,
            transport=self._transport,
        )

    async def create_order(self, amount_paise: int, receipt: str) -> str:
        try:
            async with self._client() as client:
                res = await client.post(
                    "/orders",
                    json={"amount": amount_paise, "currency": "INR", "receipt": receipt[:40]},
                )
            res.raise_for_status()
            return str(res.json()["id"])
        except (httpx.HTTPError, KeyError, ValueError) as e:
            log.error("razorpay order.create failed: %s", e)
            raise ApiError(
                "payment_unavailable",
                "Payments are unavailable right now. Your seats are still held — try again.",
                status=503,
            ) from e

    def signature_ok(self, order_id: str, payment_id: str, signature: str) -> bool:
        expected = hmac_hex(self._secret, f"{order_id}|{payment_id}".encode())
        return hmac.compare_digest(expected, signature)

    async def refund(self, payment_id: str, amount_paise: int) -> str | None:
        try:
            async with self._client() as client:
                res = await client.post(
                    f"/payments/{payment_id}/refund", json={"amount": amount_paise}
                )
            res.raise_for_status()
            return str(res.json()["id"])
        except (httpx.HTTPError, KeyError, ValueError) as e:
            # The order is still marked refunded so the customer sees why, as "refund in
            # progress"; orders.settle_refund retries it on the next read. Logged loudly.
            log.error("razorpay refund failed for %s: %s", payment_id, e)
            return None

    async def payment(self, payment_id: str) -> dict[str, Any]:
        """The payment as Razorpay has it (status, amount, currency, order_id)."""
        try:
            async with self._client() as client:
                res = await client.get(f"/payments/{payment_id}")
            res.raise_for_status()
            return dict(res.json())
        except (httpx.HTTPError, ValueError) as e:
            log.error("razorpay payment fetch failed for %s: %s", payment_id, e)
            raise ApiError(
                "payment_unavailable",
                "We couldn't confirm the payment just now. Your tickets will appear once it "
                "clears.",
                status=503,
            ) from e


class DemoGateway:
    mode: Literal["razorpay", "demo"] = "demo"
    key_id: str | None = None

    async def create_order(self, amount_paise: int, receipt: str) -> str:
        return f"demo_order_{secrets.token_hex(8)}"

    def signature_ok(self, order_id: str, payment_id: str, signature: str) -> bool:
        return False  # demo payments go through /demo-pay, never a forged signature

    async def refund(self, payment_id: str, amount_paise: int) -> str | None:
        return f"demo_refund_{secrets.token_hex(6)}"

    async def payment(self, payment_id: str) -> dict[str, Any]:
        return {}  # never reached: demo payments have no signature to verify


def gateway_for(app: FastAPI) -> Gateway:
    """The configured gateway: Razorpay when both keys are set, else the demo gateway. Tests
    put their own on `app.state.gateway`."""
    existing: Gateway | None = getattr(app.state, "gateway", None)
    if existing is not None:
        return existing
    settings: Settings = app.state.settings
    gateway: Gateway
    if settings.razorpay_key_id and settings.razorpay_key_secret:
        gateway = RazorpayGateway(
            settings.razorpay_key_id, settings.razorpay_key_secret.get_secret_value()
        )
    else:
        gateway = DemoGateway()
    app.state.gateway = gateway
    return gateway


def webhook_signature_ok(settings: Settings, body: bytes, signature: str | None) -> bool:
    if settings.razorpay_webhook_secret is None or not signature:
        return False
    expected = hmac_hex(settings.razorpay_webhook_secret.get_secret_value(), body)
    return hmac.compare_digest(expected, signature)
