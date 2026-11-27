"""show_schedules → shows → show_prices (06 §A).

A show is film + language + format + screen + start time, with a price per tier. Shows come from
schedules: an owner's bulk schedule (a bounded date range) is materialised at once; an
open-ended schedule (`to_date` null — the seeded cinemas) is materialised lazily on read so the
next 14 days always exist without a cron (B1). `UNIQUE (screen_id, starts_at)` makes concurrent
materialisation idempotent."""

import uuid
from datetime import date, datetime, time
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, CreatedMixin, UuidMixin, pg_enum
from app.models.enums import ShowStatus


class ShowSchedule(UuidMixin, CreatedMixin, Base):
    __tablename__ = "show_schedules"
    __table_args__ = (Index("ix_show_schedules_screen_id", "screen_id"),)

    screen_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("screens.id", ondelete="CASCADE"), nullable=False
    )
    film_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("films.id", ondelete="CASCADE"), nullable=False
    )
    language: Mapped[str] = mapped_column(Text, nullable=False)
    format: Mapped[str] = mapped_column(Text, nullable=False)
    days_of_week: Mapped[list[int]] = mapped_column(ARRAY(Integer), nullable=False)  # 0 = Monday
    times: Mapped[list[time]] = mapped_column(ARRAY(Time), nullable=False)  # IST wall clock
    from_date: Mapped[date] = mapped_column(Date, nullable=False)
    to_date: Mapped[date | None] = mapped_column(Date)  # null = open-ended (lazy)
    prices: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)  # {tier_key: paise}
    materialised_until: Mapped[date | None] = mapped_column(Date)
    # Seeded schedules only: the share of each new show sold to fictional bookers when it is
    # materialised, so a demo hall looks lived-in. Null for every real owner's schedule.
    seed_fill: Mapped[float | None] = mapped_column(Float)


class Show(UuidMixin, CreatedMixin, Base):
    __tablename__ = "shows"
    __table_args__ = (
        UniqueConstraint("screen_id", "starts_at"),
        Index("ix_shows_film_id_starts_at", "film_id", "starts_at"),
        Index("ix_shows_starts_at", "starts_at"),
    )

    schedule_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("show_schedules.id", ondelete="SET NULL")
    )
    screen_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("screens.id", ondelete="RESTRICT"), nullable=False
    )
    film_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("films.id", ondelete="RESTRICT"), nullable=False
    )
    language: Mapped[str] = mapped_column(Text, nullable=False)
    format: Mapped[str] = mapped_column(Text, nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[ShowStatus] = mapped_column(
        pg_enum(ShowStatus, "show_status"),
        nullable=False,
        server_default=ShowStatus.SCHEDULED.value,
    )
    cancel_reason: Mapped[str | None] = mapped_column(Text)

    prices: Mapped[list["ShowPrice"]] = relationship(
        back_populates="show", cascade="all, delete-orphan"
    )


class ShowPrice(Base):
    __tablename__ = "show_prices"

    show_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("shows.id", ondelete="CASCADE"), primary_key=True
    )
    tier_key: Mapped[str] = mapped_column(Text, primary_key=True)
    price_paise: Mapped[int] = mapped_column(Integer, nullable=False)

    show: Mapped[Show] = relationship(back_populates="prices")


class BlockedSeat(CreatedMixin, Base):
    """A seat the owner took off sale for one show (L3): customers see it unavailable; holds,
    orders and `orders.confirm` refuse it (under the per-show lock, `shows.show_lock`)."""

    __tablename__ = "blocked_seats"
    __table_args__ = (CheckConstraint("reason in ('broken', 'staff', 'guests')", name="reason"),)

    show_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("shows.id", ondelete="CASCADE"), primary_key=True
    )
    seat_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("seats.id", ondelete="RESTRICT"), primary_key=True
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
