"""Seat-map contract (06 §C/§D): `ShowtimeDetail` for the S4 header + stub, `SeatState` for the
map. Field names match 06 §D exactly — v4's app and v2's stream diff key on them."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from app.schemas import ApiModel
from app.schemas.events import EventType, Fill, TierPrice, VenueRef


class ShowtimeEvent(ApiModel):
    id: UUID
    slug: str
    title: str
    type: EventType
    genre: str
    rating: str | None
    duration_min: int
    poster_url: str


class ShowtimeVenue(VenueRef):
    template: Literal["grid", "stalls_balcony", "arena"]


class ShowtimeDetail(ApiModel):
    id: UUID
    starts_at: datetime
    status: Literal["scheduled", "cancelled"]
    event: ShowtimeEvent
    venue: ShowtimeVenue
    tiers: list[TierPrice] = Field(description="Every tier of the venue with this show's price.")
    layout_url: str = Field(description="`/venues/{id}/layout` — immutable, cache it forever.")
    fee_paise: int = Field(description="Convenience fee per ticket (03 R5: flat ₹30).")
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
