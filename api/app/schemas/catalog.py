"""Public catalogue contract (06 §C, R3/R4): home, film search, the movie page, showtimes by
cinema. Only verified businesses and now-showing films are bookable."""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from app.schemas import ApiModel

Fill = Literal["available", "filling", "sold_out"]
Cert = Literal["U", "UA", "A"]
FilmStatus = Literal["coming_soon", "now_showing", "ended"]


class CastMember(ApiModel):
    name: str = Field(min_length=1, max_length=60)
    role: str = Field(min_length=1, max_length=60, description='"Actor", "Director", …')


class FilmCard(ApiModel):
    id: UUID
    slug: str
    title: str
    cert: Cert
    runtime_min: int
    genres: list[str]
    languages: list[str]
    formats: list[str]
    poster_url: str
    banner_url: str | None
    status: FilmStatus
    release_date: date
    show_count: int = Field(description="Bookable shows in the next 14 days.")
    from_price_paise: int | None = Field(description="Cheapest ticket across those shows.")


class Version(ApiModel):
    language: str
    format: str
    show_count: int


class FilmDetail(FilmCard):
    synopsis: str
    cast_crew: list[CastMember]
    trailer_url: str | None
    versions: list[Version] = Field(description="Language × format pairs with shows on sale.")


class Home(ApiModel):
    now_showing: list[FilmCard]
    coming_soon: list[FilmCard]


class FilmList(ApiModel):
    films: list[FilmCard]
    q: str | None


class TierPrice(ApiModel):
    tier_key: str
    label: str
    price_paise: int


class ShowSlot(ApiModel):
    id: UUID
    starts_at: datetime
    screen_name: str
    language: str
    format: str
    fill: Fill
    seats_left: int
    tiers: list[TierPrice]


class CinemaShows(ApiModel):
    id: UUID
    name: str
    area: str
    address: str
    facilities: list[str]
    shows: list[ShowSlot]


class DateOption(ApiModel):
    date: date
    show_count: int


class FilmShows(ApiModel):
    film: FilmCard
    language: str | None
    format: str | None
    versions: list[Version]
    date: date
    dates: list[DateOption] = Field(description="The next 7 days, with how many shows each has.")
    cinemas: list[CinemaShows]
