"""Seat-map contract (06 §C/§D): `ShowDetail` for the booking header + stub, `SeatState` for the
map. Field names match 06 §D exactly — v4's app and v2's live updates key on them."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from app.schemas import ApiModel
from app.schemas.catalog import Cert, Fill, TierPrice


class ShowFilm(ApiModel):
    id: UUID
    slug: str
    title: str
    cert: Cert
    runtime_min: int
    poster_url: str
    genres: list[str]


class ShowCinema(ApiModel):
    id: UUID
    name: str
    area: str
    address: str


class ShowScreen(ApiModel):
    id: UUID
    name: str
    template: Literal["grid", "stalls_balcony"]
    seat_count: int


class ShowDetail(ApiModel):
    id: UUID
    starts_at: datetime
    ends_at: datetime
    language: str
    format: str
    status: Literal["scheduled", "cancelled"]
    film: ShowFilm
    cinema: ShowCinema
    screen: ShowScreen
    tiers: list[TierPrice] = Field(description="The screen's tiers with this show's prices.")
    layout_url: str = Field(description="`/screens/{id}/layout` — immutable, cache it forever.")
    fee_paise: int = Field(description="Convenience fee per ticket (R6: flat ₹30).")
    fill: Fill
    seats_left: int


class HeldSeat(ApiModel):
    seat_id: str
    expires_at: datetime


class SeatState(ApiModel):
    v: int = Field(description="State version; a diff with a lower `v` is stale.")
    server_time: datetime
    sold: list[str]
    held: list[HeldSeat] = Field(description="Held by someone else (not the caller).")
    mine: list[str] = Field(description="Held by the caller's session.")
    mine_expires_at: datetime | None = Field(
        default=None, description="When the caller's holds lapse (one shared 10-minute clock)."
    )


class HoldRequest(ApiModel):
    seat_ids: list[str] = Field(
        min_length=1,
        max_length=50,
        description="The whole current selection (POST) or the seats to let go (DELETE).",
    )


class HoldGranted(ApiModel):
    expires_at: datetime = Field(description="When these holds lapse — the countdown's zero.")
    held: list[str]
