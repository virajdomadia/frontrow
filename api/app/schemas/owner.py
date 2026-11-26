"""Theatre owner contract (06 §C, R8–R10): business, cinemas, screens from templates, film
requests, bulk scheduling, shows by day, bookings, door check-in."""

from datetime import date, datetime, time
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, field_validator

from app.schemas import ApiModel
from app.schemas.auth import BusinessStatus
from app.schemas.layouts import Knobs, Layout, LayoutTier

# v1 photos come from the bundled CC library in web/public/img (uploads are out of scope), so an
# image field is a root-relative path into it — never an arbitrary URL.
CinemaPhoto = Annotated[str, Field(pattern=r"^/img/cinemas/[a-z0-9-]+\.jpg$")]
Format = Literal["2D", "3D", "IMAX"]
FACILITIES = (
    "Dolby Atmos",
    "4K laser",
    "Recliners",
    "Wheelchair access",
    "Food court",
    "Parking",
    "M-ticket",
)
Facility = Literal[
    "Dolby Atmos", "4K laser", "Recliners", "Wheelchair access", "Food court", "Parking", "M-ticket"
]


# --- business -------------------------------------------------------------------------------------


class OwnerBusiness(ApiModel):
    id: UUID
    name: str
    slug: str
    phone: str
    status: BusinessStatus
    review_note: str | None
    created_at: datetime
    verified_at: datetime | None
    cinema_count: int
    screen_count: int
    upcoming_shows: int


class BusinessPatch(ApiModel):
    """Edit details; a rejected business that edits goes back into the approvals queue."""

    name: str = Field(min_length=2, max_length=80)
    phone: str = Field(min_length=6, max_length=20, pattern=r"^[0-9+()\- ]+$")


class RegisterBusiness(ApiModel):
    """A signed-in customer registering a business on top of their account."""

    name: str = Field(min_length=2, max_length=80)
    phone: str = Field(min_length=6, max_length=20, pattern=r"^[0-9+()\- ]+$")


# --- cinemas + screens ----------------------------------------------------------------------------


class CinemaIn(ApiModel):
    name: str = Field(min_length=2, max_length=80)
    area: str = Field(min_length=2, max_length=60, description='Neighbourhood, e.g. "Indiranagar".')
    address: str = Field(min_length=6, max_length=200)
    facilities: list[Facility] = Field(default_factory=list, max_length=len(FACILITIES))
    photo_url: CinemaPhoto | None = None


class OwnerScreen(ApiModel):
    id: UUID
    cinema_id: UUID
    name: str
    template: Literal["grid", "stalls_balcony"]
    seat_count: int
    formats: list[str]
    tiers: list[LayoutTier]
    upcoming_shows: int


class OwnerScreenDetail(OwnerScreen):
    knobs: dict[str, object]
    layout: Layout


class OwnerCinema(ApiModel):
    id: UUID
    name: str
    area: str
    address: str
    facilities: list[str]
    photo_url: str | None
    screens: list[OwnerScreen]
    upcoming_shows: int
    created_at: datetime


class ScreenIn(ApiModel):
    name: str = Field(min_length=1, max_length=40)
    formats: list[Format] = Field(min_length=1, max_length=3)
    knobs: Knobs

    @field_validator("formats")
    @classmethod
    def _unique(cls, v: list[str]) -> list[str]:
        return list(dict.fromkeys(v))


class ScreenPreview(ApiModel):
    knobs: Knobs


# --- films ----------------------------------------------------------------------------------------


class FilmRef(ApiModel):
    id: UUID
    slug: str
    title: str


class FilmRequestIn(ApiModel):
    title: str = Field(min_length=1, max_length=120)
    note: str | None = Field(default=None, max_length=500, description="Language, release, …")


class OwnerFilmRequest(ApiModel):
    id: UUID
    title: str
    note: str | None
    status: Literal["open", "added", "declined"]
    reply: str | None
    film: FilmRef | None
    created_at: datetime


# --- shows ----------------------------------------------------------------------------------------


class BulkShows(ApiModel):
    screen_id: UUID
    film_id: UUID
    language: str = Field(min_length=1, max_length=30)
    format: Format
    days: list[Annotated[int, Field(ge=0, le=6)]] = Field(
        min_length=1, max_length=7, description="0 = Monday … 6 = Sunday"
    )
    times: list[time] = Field(min_length=1, max_length=8, description="IST start times")
    from_date: date
    to_date: date
    prices: dict[str, Annotated[int, Field(ge=5000, le=200000)]] = Field(
        description="`{tier_key: paise}` for every tier of the screen (₹50–₹2,000)."
    )


class ShowFilmRef(ApiModel):
    id: UUID
    slug: str
    title: str
    poster_url: str
    runtime_min: int


class OwnerShow(ApiModel):
    id: UUID
    starts_at: datetime
    ends_at: datetime
    status: Literal["scheduled", "cancelled"]
    film: ShowFilmRef
    language: str
    format: str
    cinema_name: str
    screen_id: UUID
    screen_name: str
    seat_count: int
    sold: int
    checked_in: int
    revenue_paise: int = Field(description="Ticket sales for the cinema (excludes the fee).")
    public: bool = Field(description="Customers can see it (business verified, film showing).")


class BulkResult(ApiModel):
    created: int
    first: datetime
    last: datetime
    shows: list[OwnerShow] = Field(description="The first few, soonest first.")


class DayCount(ApiModel):
    date: date
    show_count: int


class OwnerShows(ApiModel):
    date: date
    dates: list[DayCount] = Field(description="The next 14 days with how many shows each has.")
    shows: list[OwnerShow]


class Booking(ApiModel):
    order_id: UUID
    name: str
    email: str
    seats: list[str]
    tier_labels: list[str]
    amount_paise: int
    payment_method: str | None
    paid_at: datetime | None
    checked_in: int


class Bookings(ApiModel):
    show: OwnerShow
    bookings: list[Booking]


# --- door -----------------------------------------------------------------------------------------


class CheckIn(ApiModel):
    token: str = Field(min_length=10, max_length=300, description="What the QR encodes.")
    show_id: UUID


class CheckInResult(ApiModel):
    result: Literal["valid", "used", "wrong_show", "invalid"]
    message: str
    seat: str | None = None
    name: str | None = None
    checked_in_at: datetime | None = None
    admitted: int = Field(description="Tickets scanned in for this show so far.")
    sold: int
