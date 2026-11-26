"""Orders and tickets contract (06 §C): `Order`, `TicketBundle`, `MyTickets`."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from app.schemas import ApiModel
from app.schemas.events import EventType

OrderStatus = Literal["pending", "paid", "expired", "refunded", "failed"]
GatewayMode = Literal["razorpay", "demo"]


class CreateOrder(ApiModel):
    showtime_id: UUID
    seat_ids: list[str] = Field(min_length=1, max_length=10)


class VerifyPayment(ApiModel):
    razorpay_payment_id: str = Field(min_length=1, max_length=64)
    razorpay_signature: str = Field(min_length=1, max_length=256)


class OrderEvent(ApiModel):
    slug: str
    title: str
    type: EventType
    poster_url: str
    duration_min: int
    rating: str | None


class OrderVenue(ApiModel):
    id: UUID
    name: str
    address: str


class OrderShowtime(ApiModel):
    id: UUID
    starts_at: datetime
    ends_at: datetime
    event: OrderEvent
    venue: OrderVenue


class OrderSeatOut(ApiModel):
    seat_id: str
    label: str = Field(description='"G9", or "Section 3 · C7" in an arena.')
    tier_key: str
    tier_label: str
    price_paise: int


class Customer(ApiModel):
    name: str
    email: str


class Order(ApiModel):
    id: UUID
    status: OrderStatus
    showtime: OrderShowtime
    seats: list[OrderSeatOut]
    subtotal_paise: int
    fee_paise: int
    total_paise: int
    created_at: datetime
    paid_at: datetime | None
    pay_by: datetime = Field(description="A pending order expires 15 minutes after creation.")
    hold_expires_at: datetime | None = Field(
        description="While pending: when the seat holds lapse (the checkout countdown)."
    )
    refund_reason: str | None = Field(description="`seat_sold` when paid after the hold lapsed.")
    gateway: GatewayMode = Field(
        description="`razorpay` → open Razorpay Checkout with `key_id`; `demo` → no keys are "
        "configured, pay with `POST /orders/{id}/demo-pay` (test mode, no money moves)."
    )
    razorpay_order_id: str | None
    key_id: str | None
    customer: Customer


class TicketOut(ApiModel):
    id: UUID
    seat_id: str
    label: str
    tier_label: str
    qr_token: str = Field(description="Signed token the QR encodes; the door verifies it.")
    checked_in_at: datetime | None


class TicketBundle(ApiModel):
    order: Order
    tickets: list[TicketOut]


class TicketGroup(ApiModel):
    order_id: UUID
    showtime: OrderShowtime
    seats: list[str]
    tier_labels: list[str]
    total_paise: int
    paid_at: datetime | None


class MyTickets(ApiModel):
    upcoming: list[TicketGroup]
    past: list[TicketGroup]
