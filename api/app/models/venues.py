"""venues + seats (06 §A). A venue is generated once from a template + knobs; `layout` is the
JSON the seat map renders and `seats` are rows because holds, tickets and the heatmap key on
`seat_id`."""

import uuid
from typing import Any

from sqlalchemy import ForeignKey, Index, Integer, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, CreatedMixin, UuidMixin, pg_enum
from app.models.enums import LayoutTemplate


class Venue(UuidMixin, CreatedMixin, Base):
    __tablename__ = "venues"
    __table_args__ = (Index("ix_venues_organiser_id", "organiser_id"),)

    organiser_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    address: Mapped[str] = mapped_column(Text, nullable=False)
    photo_url: Mapped[str | None] = mapped_column(Text)
    template: Mapped[LayoutTemplate] = mapped_column(
        pg_enum(LayoutTemplate, "layout_template"), nullable=False
    )
    knobs: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    layout: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    seat_count: Mapped[int] = mapped_column(Integer, nullable=False)

    seats: Mapped[list["Seat"]] = relationship(back_populates="venue")


class Seat(UuidMixin, Base):
    __tablename__ = "seats"
    __table_args__ = (
        UniqueConstraint("venue_id", "section_key", "row_label", "number"),
        Index("ix_seats_venue_id", "venue_id"),
    )

    venue_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("venues.id", ondelete="CASCADE"), nullable=False
    )
    section_key: Mapped[str] = mapped_column(Text, nullable=False)
    row_label: Mapped[str] = mapped_column(Text, nullable=False)
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    tier_key: Mapped[str] = mapped_column(Text, nullable=False)
    x: Mapped[int] = mapped_column(Integer, nullable=False)
    y: Mapped[int] = mapped_column(Integer, nullable=False)

    venue: Mapped[Venue] = relationship(back_populates="seats")
