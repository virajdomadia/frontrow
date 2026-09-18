"""SQLAlchemy 2.0 declarative models — one module per table group (06 §A).

Import this package (not the modules) wherever the full metadata is needed: Alembic's env.py and
the test harness rely on every model being registered on `Base.metadata`.
"""

from app.models.auth import Session, User
from app.models.base import Base
from app.models.events import Event, PriceTier, Showtime
from app.models.orders import Order, OrderSeat, Ticket, WebhookEvent
from app.models.venues import Seat, Venue

__all__ = [
    "Base",
    "Event",
    "Order",
    "OrderSeat",
    "PriceTier",
    "Seat",
    "Session",
    "Showtime",
    "Ticket",
    "User",
    "Venue",
    "WebhookEvent",
]
