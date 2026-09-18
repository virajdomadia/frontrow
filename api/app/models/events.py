"""events + showtimes + price_tiers (06 §A)."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, CreatedMixin, UuidMixin, pg_enum
from app.models.enums import EventStatus, EventType, ShowtimeStatus
from app.models.venues import Venue


class Event(UuidMixin, CreatedMixin, Base):
    __tablename__ = "events"
    __table_args__ = (Index("ix_events_status_type", "status", "type"),)

    organiser_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    slug: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[EventType] = mapped_column(pg_enum(EventType, "event_type"), nullable=False)
    genre: Mapped[str] = mapped_column(Text, nullable=False)
    duration_min: Mapped[int] = mapped_column(Integer, nullable=False)
    rating: Mapped[str | None] = mapped_column(Text)  # movies: U / UA / UA 16+ / A
    synopsis: Mapped[str] = mapped_column(Text, nullable=False)
    cast_lineup: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    poster_url: Mapped[str] = mapped_column(Text, nullable=False)
    gallery_urls: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    status: Mapped[EventStatus] = mapped_column(
        pg_enum(EventStatus, "event_status"), nullable=False, server_default=EventStatus.DRAFT.value
    )

    showtimes: Mapped[list["Showtime"]] = relationship(back_populates="event")


class Showtime(UuidMixin, CreatedMixin, Base):
    __tablename__ = "showtimes"
    __table_args__ = (
        Index("ix_showtimes_starts_at", "starts_at"),
        Index("ix_showtimes_event_id_starts_at", "event_id", "starts_at"),
        Index("ix_showtimes_venue_id_starts_at", "venue_id", "starts_at"),
    )

    event_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), nullable=False
    )
    venue_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("venues.id", ondelete="RESTRICT"), nullable=False
    )
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[ShowtimeStatus] = mapped_column(
        pg_enum(ShowtimeStatus, "showtime_status"),
        nullable=False,
        server_default=ShowtimeStatus.SCHEDULED.value,
    )

    event: Mapped[Event] = relationship(back_populates="showtimes")
    venue: Mapped[Venue] = relationship()
    tiers: Mapped[list["PriceTier"]] = relationship(
        back_populates="showtime", cascade="all, delete-orphan"
    )


class PriceTier(Base):
    __tablename__ = "price_tiers"

    showtime_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("showtimes.id", ondelete="CASCADE"), primary_key=True
    )
    tier_key: Mapped[str] = mapped_column(Text, primary_key=True)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    price_paise: Mapped[int] = mapped_column(Integer, nullable=False)

    showtime: Mapped[Showtime] = relationship(back_populates="tiers")
