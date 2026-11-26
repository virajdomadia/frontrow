"""Organiser console contract (06 §C, R8): venues from templates, events, showtimes, bookings."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field

from app.schemas import ApiModel
from app.schemas.events import EventType, TierPrice
from app.schemas.layouts import Knobs, Layout, LayoutTier

# v1 posters and venue photos come from the bundled CC library in web/public/img (uploads are
# v2), so an image field is a root-relative path into it — never an arbitrary URL.
ImagePath = Annotated[str, Field(pattern=r"^/img/(posters|venues)/[a-z0-9-]+\.jpg$")]
Template = Literal["grid", "stalls_balcony", "arena"]
EventStatus = Literal["draft", "live"]


# --- venues ---------------------------------------------------------------------------------------


class VenuePreview(ApiModel):
    knobs: Knobs


class CreateVenue(ApiModel):
    name: str = Field(min_length=2, max_length=80)
    address: str = Field(min_length=4, max_length=200)
    photo_url: ImagePath | None = None
    knobs: Knobs


class OrganiserVenue(ApiModel):
    id: UUID
    name: str
    address: str
    photo_url: str | None
    template: Template
    seat_count: int
    tiers: list[LayoutTier]
    upcoming_showtimes: int
    created_at: datetime


class OrganiserVenueDetail(OrganiserVenue):
    knobs: dict[str, object]
    layout: Layout


# --- events ---------------------------------------------------------------------------------------


class EventFields(ApiModel):
    title: str = Field(min_length=2, max_length=80)
    type: EventType
    genre: str = Field(min_length=2, max_length=40)
    duration_min: int = Field(ge=30, le=400)
    rating: str | None = Field(default=None, max_length=12)
    synopsis: str = Field(min_length=10, max_length=1200)
    cast_lineup: list[Annotated[str, Field(min_length=1, max_length=80)]] = Field(
        default_factory=list, max_length=12
    )
    poster_url: ImagePath
    gallery_urls: list[ImagePath] = Field(default_factory=list, max_length=6)
    status: EventStatus = "live"


class EventPatch(ApiModel):
    title: str | None = Field(default=None, min_length=2, max_length=80)
    type: EventType | None = None
    genre: str | None = Field(default=None, min_length=2, max_length=40)
    duration_min: int | None = Field(default=None, ge=30, le=400)
    rating: str | None = Field(default=None, max_length=12)
    synopsis: str | None = Field(default=None, min_length=10, max_length=1200)
    cast_lineup: list[Annotated[str, Field(min_length=1, max_length=80)]] | None = Field(
        default=None, max_length=12
    )
    poster_url: ImagePath | None = None
    gallery_urls: list[ImagePath] | None = Field(default=None, max_length=6)
    status: EventStatus | None = None


class OrganiserEvent(EventFields):
    id: UUID
    slug: str
    upcoming_showtimes: int
    tickets_sold: int
    created_at: datetime


# --- showtimes ------------------------------------------------------------------------------------


class TierInput(ApiModel):
    tier_key: str = Field(min_length=1, max_length=24)
    label: str | None = Field(default=None, max_length=40)
    price_paise: int = Field(ge=1000, le=10_000_000, description="₹10 – ₹1,00,000")


class CreateShowtime(ApiModel):
    event_id: UUID
    venue_id: UUID
    starts_at: datetime
    tiers: list[TierInput] = Field(min_length=1, max_length=8)


class ShowtimePatch(ApiModel):
    status: Literal["scheduled", "cancelled"] | None = None
    starts_at: datetime | None = None


class ShowtimeEventRef(ApiModel):
    id: UUID
    slug: str
    title: str
    type: EventType
    status: EventStatus


class ShowtimeVenueRef(ApiModel):
    id: UUID
    name: str
    template: Template


class OrganiserShowtime(ApiModel):
    id: UUID
    starts_at: datetime
    status: Literal["scheduled", "cancelled"]
    event: ShowtimeEventRef
    venue: ShowtimeVenueRef
    tiers: list[TierPrice]
    seat_count: int
    sold: int
    revenue_paise: int = Field(description="Ticket revenue excluding convenience fees.")


# --- bookings -------------------------------------------------------------------------------------


class Booking(ApiModel):
    order_id: UUID
    customer_name: str
    customer_email: str
    seats: list[str]
    tier_labels: list[str]
    tickets: int
    subtotal_paise: int
    total_paise: int
    paid_at: datetime | None


class Bookings(ApiModel):
    showtime: OrganiserShowtime
    bookings: list[Booking]
    tickets: int
    revenue_paise: int
