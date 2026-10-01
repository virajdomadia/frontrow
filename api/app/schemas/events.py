"""Public catalog contract (06 §C): `EventCard`, `EventDetail`, `ShowtimeSummary`."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from app.schemas import ApiModel

Fill = Literal["available", "filling", "sold_out"]
EventType = Literal["movie", "concert"]
DatePreset = Literal["today", "tomorrow", "weekend"]
Sort = Literal["soonest", "price", "title"]


class VenueRef(ApiModel):
    id: UUID
    name: str
    address: str
    seat_count: int
    photo_url: str | None


class NextShowtime(ApiModel):
    id: UUID
    starts_at: datetime
    venue_name: str
    fill: Fill


class EventCard(ApiModel):
    id: UUID
    slug: str
    title: str
    type: EventType
    genre: str
    rating: str | None
    duration_min: int
    poster_url: str
    from_price_paise: int | None = Field(description="Cheapest tier across upcoming showtimes.")
    next_showtime: NextShowtime | None
    upcoming_count: int = Field(description="Upcoming showtimes matching the list's date filter.")


class FilterOption(ApiModel):
    value: str
    label: str
    count: int


class EventList(ApiModel):
    events: list[EventCard]
    total: int
    showtime_count: int
    genres: list[FilterOption]
    venues: list[FilterOption]


class TierPrice(ApiModel):
    tier_key: str
    label: str
    price_paise: int


class ShowtimeSummary(ApiModel):
    id: UUID
    starts_at: datetime
    venue: VenueRef
    tiers: list[TierPrice]
    price_min_paise: int
    price_max_paise: int
    fill: Fill
    seats_left: int


class EventDetail(EventCard):
    synopsis: str
    cast_lineup: list[str]
    gallery_urls: list[str]
    showtimes: list[ShowtimeSummary]


class Home(ApiModel):
    now_showing: list[EventCard]
