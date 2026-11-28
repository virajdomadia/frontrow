"""SQLAlchemy 2.0 declarative models — one module per table group (06 §A).

Import this package (not the modules) wherever the full metadata is needed: Alembic's env.py and
the test harness rely on every model being registered on `Base.metadata`.
"""

from app.models.auth import Session, User
from app.models.base import Base
from app.models.business import Business, BusinessMember, Cinema, Screen, Seat
from app.models.films import Film, FilmRequest
from app.models.orders import EmailOutbox, Order, OrderSeat, Ticket, WebhookEvent
from app.models.shows import BlockedSeat, Show, ShowPrice, ShowSchedule

__all__ = [
    "Base",
    "BlockedSeat",
    "Business",
    "BusinessMember",
    "Cinema",
    "EmailOutbox",
    "Film",
    "FilmRequest",
    "Order",
    "OrderSeat",
    "Screen",
    "Seat",
    "Session",
    "Show",
    "ShowPrice",
    "ShowSchedule",
    "Ticket",
    "User",
    "WebhookEvent",
]
