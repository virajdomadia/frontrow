"""Frontrow staff contract (06 §C 🛠, R11): the film catalogue, film requests, approvals."""

from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, field_validator

from app.schemas import ApiModel
from app.schemas.auth import BusinessStatus
from app.schemas.catalog import CastMember, Cert, FilmCard, FilmStatus
from app.schemas.owner import FilmRef

# Posters come from the bundled CC library (uploads are out of scope in v1).
Poster = Annotated[str, Field(pattern=r"^/img/posters/[a-z0-9-]+\.(jpg|png)$")]
Trailer = Annotated[
    str, Field(pattern=r"^https://(www\.)?(youtube\.com|youtu\.be|vimeo\.com)/\S+$")
]
Short = Annotated[str, Field(min_length=1, max_length=30)]


class FilmIn(ApiModel):
    title: str = Field(min_length=1, max_length=120)
    synopsis: str = Field(min_length=20, max_length=1500)
    cast_crew: list[CastMember] = Field(min_length=1, max_length=20)
    runtime_min: int | None = Field(default=None, ge=40, le=240, description="Null: not announced.")
    cert: Cert | None = Field(default=None, description="Null: not yet certified.")
    genres: list[Short] = Field(min_length=1, max_length=4)
    languages: list[Short] = Field(min_length=1, max_length=6)
    formats: list[Literal["2D", "3D", "IMAX"]] = Field(min_length=1, max_length=3)
    poster_url: Poster
    banner_url: Poster | None = None
    trailer_url: Trailer | None = None
    release_date: date
    status: FilmStatus
    request_id: UUID | None = Field(
        default=None, description="Add the film an owner asked for: the request is linked."
    )

    @field_validator("genres", "languages", "formats")
    @classmethod
    def _unique(cls, v: list[str]) -> list[str]:
        return list(dict.fromkeys(x.strip() for x in v))


class StaffFilm(FilmCard):
    synopsis: str
    cast_crew: list[CastMember]
    trailer_url: str | None
    created_at: datetime
    scheduled_shows: int = Field(description="Upcoming shows across every cinema.")


class StaffBusinessRef(ApiModel):
    id: UUID
    name: str


class StaffFilmRequest(ApiModel):
    id: UUID
    title: str
    note: str | None
    status: Literal["open", "added", "declined"]
    reply: str | None
    business: StaffBusinessRef
    film: FilmRef | None
    created_at: datetime


class RequestDecision(ApiModel):
    action: Literal["decline", "link"]
    reply: str | None = Field(default=None, max_length=300, description="Why, on a decline.")
    film_id: UUID | None = Field(default=None, description="An existing film, on a link.")


class Person(ApiModel):
    name: str
    email: str


class StaffCinema(ApiModel):
    id: UUID
    name: str
    area: str
    address: str
    screens: int
    seats: int


class StaffBusiness(ApiModel):
    id: UUID
    name: str
    slug: str
    phone: str
    status: BusinessStatus
    review_note: str | None
    created_at: datetime
    verified_at: datetime | None
    owners: list[Person]
    cinemas: list[StaffCinema]
    scheduled_shows: int


class BusinessDecision(ApiModel):
    action: Literal["approve", "reject"]
    note: str | None = Field(default=None, max_length=300, description="Required to reject.")


class StaffCounts(ApiModel):
    pending_businesses: int
    open_requests: int
    films: int


class OutboxItem(ApiModel):
    """One customer email (L5): what was or would have been sent, and why it was or wasn't."""

    id: UUID
    to: str = Field(description="Masked for the demo staff account.")
    subject: str
    body: str
    kind: str
    status: Literal["queued", "sent", "failed", "not_sent", "logged", "skipped"]
    error: str | None
    order_id: UUID | None
    created_at: datetime
    sent_at: datetime | None
