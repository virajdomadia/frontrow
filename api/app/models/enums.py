"""The Postgres enums of the movies-only model (06 §A). Values are what is stored."""

from enum import StrEnum


class SessionKind(StrEnum):
    WEB = "web"
    MOBILE = "mobile"


class Cert(StrEnum):
    U = "U"
    UA = "UA"
    A = "A"


class FilmStatus(StrEnum):
    COMING_SOON = "coming_soon"
    NOW_SHOWING = "now_showing"
    ENDED = "ended"


class BusinessStatus(StrEnum):
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"
    SUSPENDED = "suspended"  # v2


class LayoutTemplate(StrEnum):
    GRID = "grid"
    STALLS_BALCONY = "stalls_balcony"


class ShowStatus(StrEnum):
    SCHEDULED = "scheduled"
    CANCELLED = "cancelled"


class OrderStatus(StrEnum):
    PENDING = "pending"
    PAID = "paid"
    EXPIRED = "expired"
    REFUNDED = "refunded"
    FAILED = "failed"


class OrderChannel(StrEnum):
    ONLINE = "online"
    COUNTER = "counter"  # v2


class RequestStatus(StrEnum):
    OPEN = "open"
    ADDED = "added"
    DECLINED = "declined"
