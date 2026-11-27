"""The shared film catalogue (06 §A, PRD decision 4): staff create every film once; theatre
owners schedule shows of it and request the ones that are missing."""

import uuid
from datetime import date
from typing import Any

from sqlalchemy import Date, ForeignKey, Index, Integer, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedMixin, UuidMixin, pg_enum
from app.models.enums import Cert, FilmStatus, RequestStatus


class Film(UuidMixin, CreatedMixin, Base):
    __tablename__ = "films"
    __table_args__ = (Index("ix_films_status", "status"),)

    slug: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    synopsis: Mapped[str] = mapped_column(Text, nullable=False)
    cast_crew: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)  # name, role
    runtime_min: Mapped[int | None] = mapped_column(Integer)  # null: not announced yet
    cert: Mapped[Cert | None] = mapped_column(pg_enum(Cert, "cert"))  # null: not yet certified
    genres: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    languages: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    formats: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    poster_url: Mapped[str] = mapped_column(Text, nullable=False)
    banner_url: Mapped[str | None] = mapped_column(Text)
    trailer_url: Mapped[str | None] = mapped_column(Text)
    release_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[FilmStatus] = mapped_column(pg_enum(FilmStatus, "film_status"), nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )


class FilmRequest(UuidMixin, CreatedMixin, Base):
    __tablename__ = "film_requests"
    __table_args__ = (Index("ix_film_requests_status", "status"),)

    business_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    status: Mapped[RequestStatus] = mapped_column(
        pg_enum(RequestStatus, "request_status"),
        nullable=False,
        server_default=RequestStatus.OPEN.value,
    )
    film_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("films.id", ondelete="SET NULL"))
    reply: Mapped[str | None] = mapped_column(Text)  # the reason on a decline
