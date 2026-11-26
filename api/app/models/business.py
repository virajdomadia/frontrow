"""businesses → cinemas → screens → seats (06 §A).

A business (a cinema chain or a single screen) is verified once by staff before anything it
builds goes public. A screen is generated once from a layout template + knobs: `layout` is the
JSON the seat map renders and `seats` are rows because holds, tickets and the heatmap key on
`seat_id`."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, CreatedMixin, UuidMixin, pg_enum
from app.models.enums import BusinessStatus, LayoutTemplate


class Business(UuidMixin, CreatedMixin, Base):
    __tablename__ = "businesses"

    name: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    phone: Mapped[str] = mapped_column(Text, nullable=False)
    logo_url: Mapped[str | None] = mapped_column(Text)
    status: Mapped[BusinessStatus] = mapped_column(
        pg_enum(BusinessStatus, "business_status"),
        nullable=False,
        server_default=BusinessStatus.PENDING.value,
    )
    review_note: Mapped[str | None] = mapped_column(Text)  # the reason on a rejection
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    cinemas: Mapped[list["Cinema"]] = relationship(back_populates="business")


class BusinessMember(Base):
    __tablename__ = "business_members"
    __table_args__ = (Index("ix_business_members_user_id", "user_id"),)

    business_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("businesses.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[str] = mapped_column(Text, nullable=False, server_default="owner")  # usher later


class Cinema(UuidMixin, CreatedMixin, Base):
    __tablename__ = "cinemas"
    __table_args__ = (Index("ix_cinemas_business_id", "business_id"),)

    business_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    area: Mapped[str] = mapped_column(Text, nullable=False)
    address: Mapped[str] = mapped_column(Text, nullable=False)
    facilities: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    photo_url: Mapped[str | None] = mapped_column(Text)

    business: Mapped[Business] = relationship(back_populates="cinemas")
    screens: Mapped[list["Screen"]] = relationship(back_populates="cinema")


class Screen(UuidMixin, CreatedMixin, Base):
    __tablename__ = "screens"
    __table_args__ = (Index("ix_screens_cinema_id", "cinema_id"),)

    cinema_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cinemas.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    template: Mapped[LayoutTemplate] = mapped_column(
        pg_enum(LayoutTemplate, "layout_template"), nullable=False
    )
    knobs: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    layout: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    tiers: Mapped[list[dict[str, str]]] = mapped_column(JSONB, nullable=False)  # [{key, label}]
    formats: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    seat_count: Mapped[int] = mapped_column(Integer, nullable=False)

    cinema: Mapped[Cinema] = relationship(back_populates="screens")
    seats: Mapped[list["Seat"]] = relationship(back_populates="screen")


class Seat(UuidMixin, Base):
    __tablename__ = "seats"
    __table_args__ = (
        UniqueConstraint("screen_id", "section_key", "row_label", "number"),
        Index("ix_seats_screen_id", "screen_id"),
    )

    screen_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("screens.id", ondelete="CASCADE"), nullable=False
    )
    section_key: Mapped[str] = mapped_column(Text, nullable=False)
    row_label: Mapped[str] = mapped_column(Text, nullable=False)
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    tier_key: Mapped[str] = mapped_column(Text, nullable=False)
    x: Mapped[int] = mapped_column(Integer, nullable=False)
    y: Mapped[int] = mapped_column(Integer, nullable=False)

    screen: Mapped[Screen] = relationship(back_populates="seats")
