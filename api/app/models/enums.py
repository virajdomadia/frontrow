"""The six Postgres enums (06 §A). Values are what is stored."""

from enum import StrEnum


class UserRole(StrEnum):
    CUSTOMER = "customer"
    ORGANISER = "organiser"


class SessionKind(StrEnum):
    WEB = "web"
    MOBILE = "mobile"


class EventType(StrEnum):
    MOVIE = "movie"
    CONCERT = "concert"


class EventStatus(StrEnum):
    DRAFT = "draft"
    LIVE = "live"


class ShowtimeStatus(StrEnum):
    SCHEDULED = "scheduled"
    CANCELLED = "cancelled"


class OrderStatus(StrEnum):
    PENDING = "pending"
    PAID = "paid"
    EXPIRED = "expired"
    REFUNDED = "refunded"
    FAILED = "failed"


class LayoutTemplate(StrEnum):
    GRID = "grid"
    STALLS_BALCONY = "stalls_balcony"
    ARENA = "arena"
