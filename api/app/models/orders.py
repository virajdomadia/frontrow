"""orders + order_seats + tickets + webhook_events (06 §A).

`tickets` carries the one constraint the whole engine leans on: UNIQUE (showtime_id, seat_id) —
the final guard on confirm, so even a Redis mishap cannot double-sell.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, CreatedMixin, UuidMixin, pg_enum
from app.models.enums import OrderStatus


class Order(UuidMixin, CreatedMixin, Base):
    __tablename__ = "orders"
    __table_args__ = (
        Index("ix_orders_user_id_created_at", "user_id", "created_at"),
        Index("ix_orders_showtime_id_status", "showtime_id", "status"),
    )

    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    sid: Mapped[str] = mapped_column(Text, nullable=False)
    showtime_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("showtimes.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[OrderStatus] = mapped_column(
        pg_enum(OrderStatus, "order_status"), nullable=False
    )
    subtotal_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    fee_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    total_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    razorpay_order_id: Mapped[str | None] = mapped_column(Text, unique=True)
    razorpay_payment_id: Mapped[str | None] = mapped_column(Text)
    refund_id: Mapped[str | None] = mapped_column(Text)
    refund_reason: Mapped[str | None] = mapped_column(Text)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    seats: Mapped[list["OrderSeat"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )
    tickets: Mapped[list["Ticket"]] = relationship(back_populates="order")


class OrderSeat(Base):
    """Freezes the price at order time (v3 dynamic pricing needs this)."""

    __tablename__ = "order_seats"

    order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), primary_key=True
    )
    seat_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("seats.id", ondelete="RESTRICT"), primary_key=True
    )
    tier_key: Mapped[str] = mapped_column(Text, nullable=False)
    price_paise: Mapped[int] = mapped_column(Integer, nullable=False)

    order: Mapped[Order] = relationship(back_populates="seats")


class Ticket(UuidMixin, CreatedMixin, Base):
    __tablename__ = "tickets"
    __table_args__ = (
        UniqueConstraint("showtime_id", "seat_id"),
        Index("ix_tickets_user_id", "user_id"),
        Index("ix_tickets_order_id", "order_id"),
    )

    order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    showtime_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("showtimes.id", ondelete="CASCADE"), nullable=False
    )
    seat_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("seats.id", ondelete="RESTRICT"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    checked_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    order: Mapped[Order] = relationship(back_populates="tickets")


class WebhookEvent(Base):
    """Razorpay event id; a duplicate insert = replay, so the handler does nothing."""

    __tablename__ = "webhook_events"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
