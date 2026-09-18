"""v1 — enums, users + sessions, venues + seats, events + showtimes + price_tiers, orders +
order_seats + tickets + webhook_events, and the showtime_fill view (06 §A).

Revision ID: 0001
Revises:
Create Date: 2026-09-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Native enums are created and dropped explicitly so `downgrade base` leaves nothing behind.
ENUMS = {
    "user_role": ("customer", "organiser"),
    "session_kind": ("web", "mobile"),
    "event_type": ("movie", "concert"),
    "event_status": ("draft", "live"),
    "showtime_status": ("scheduled", "cancelled"),
    "order_status": ("pending", "paid", "expired", "refunded", "failed"),
    "layout_template": ("grid", "stalls_balcony", "arena"),
}


def _enum(name: str) -> postgresql.ENUM:
    return postgresql.ENUM(*ENUMS[name], name=name, create_type=False)


def _created_at() -> sa.Column:
    return sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        server_default=sa.text("now()"),
        nullable=False,
    )


# Fill per showtime (event page badge, dashboard). Held counts come from Redis, merged in the API.
SHOWTIME_FILL = """
create view showtime_fill as
select s.id as showtime_id, v.seat_count, count(t.id)::int as sold
from showtimes s
join venues v on v.id = s.venue_id
left join tickets t on t.showtime_id = s.id
group by s.id, v.seat_count
"""


def upgrade() -> None:
    bind = op.get_bind()
    for name in ENUMS:
        _enum(name).create(bind)

    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("role", _enum("user_role"), nullable=False),
        _created_at(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )

    op.create_table(
        "sessions",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("sid", sa.Text(), nullable=True),
        sa.Column("kind", _enum("session_kind"), server_default="web", nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        _created_at(),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_sessions_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sessions")),
    )
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])

    op.create_table(
        "venues",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organiser_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("address", sa.Text(), nullable=False),
        sa.Column("photo_url", sa.Text(), nullable=True),
        sa.Column("template", _enum("layout_template"), nullable=False),
        sa.Column("knobs", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("layout", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("seat_count", sa.Integer(), nullable=False),
        _created_at(),
        sa.ForeignKeyConstraint(
            ["organiser_id"],
            ["users.id"],
            name=op.f("fk_venues_organiser_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_venues")),
    )
    op.create_index("ix_venues_organiser_id", "venues", ["organiser_id"])

    op.create_table(
        "seats",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("venue_id", sa.Uuid(), nullable=False),
        sa.Column("section_key", sa.Text(), nullable=False),
        sa.Column("row_label", sa.Text(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("tier_key", sa.Text(), nullable=False),
        sa.Column("x", sa.Integer(), nullable=False),
        sa.Column("y", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["venue_id"], ["venues.id"], name=op.f("fk_seats_venue_id_venues"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_seats")),
        sa.UniqueConstraint(
            "venue_id",
            "section_key",
            "row_label",
            "number",
            name=op.f("uq_seats_venue_id_section_key_row_label_number"),
        ),
    )
    op.create_index("ix_seats_venue_id", "seats", ["venue_id"])

    op.create_table(
        "events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organiser_id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("type", _enum("event_type"), nullable=False),
        sa.Column("genre", sa.Text(), nullable=False),
        sa.Column("duration_min", sa.Integer(), nullable=False),
        sa.Column("rating", sa.Text(), nullable=True),
        sa.Column("synopsis", sa.Text(), nullable=False),
        sa.Column("cast_lineup", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("poster_url", sa.Text(), nullable=False),
        sa.Column("gallery_urls", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("status", _enum("event_status"), server_default="draft", nullable=False),
        _created_at(),
        sa.ForeignKeyConstraint(
            ["organiser_id"],
            ["users.id"],
            name=op.f("fk_events_organiser_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_events")),
        sa.UniqueConstraint("slug", name=op.f("uq_events_slug")),
    )
    op.create_index("ix_events_status_type", "events", ["status", "type"])

    op.create_table(
        "showtimes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("venue_id", sa.Uuid(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", _enum("showtime_status"), server_default="scheduled", nullable=False),
        _created_at(),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["events.id"],
            name=op.f("fk_showtimes_event_id_events"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["venue_id"],
            ["venues.id"],
            name=op.f("fk_showtimes_venue_id_venues"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_showtimes")),
    )
    op.create_index("ix_showtimes_starts_at", "showtimes", ["starts_at"])
    op.create_index("ix_showtimes_event_id_starts_at", "showtimes", ["event_id", "starts_at"])
    op.create_index("ix_showtimes_venue_id_starts_at", "showtimes", ["venue_id", "starts_at"])

    op.create_table(
        "price_tiers",
        sa.Column("showtime_id", sa.Uuid(), nullable=False),
        sa.Column("tier_key", sa.Text(), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("price_paise", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["showtime_id"],
            ["showtimes.id"],
            name=op.f("fk_price_tiers_showtime_id_showtimes"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("showtime_id", "tier_key", name=op.f("pk_price_tiers")),
    )

    op.create_table(
        "orders",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("sid", sa.Text(), nullable=False),
        sa.Column("showtime_id", sa.Uuid(), nullable=False),
        sa.Column("status", _enum("order_status"), nullable=False),
        sa.Column("subtotal_paise", sa.Integer(), nullable=False),
        sa.Column("fee_paise", sa.Integer(), nullable=False),
        sa.Column("total_paise", sa.Integer(), nullable=False),
        sa.Column("razorpay_order_id", sa.Text(), nullable=True),
        sa.Column("razorpay_payment_id", sa.Text(), nullable=True),
        sa.Column("refund_id", sa.Text(), nullable=True),
        sa.Column("refund_reason", sa.Text(), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        _created_at(),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_orders_user_id_users"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["showtime_id"],
            ["showtimes.id"],
            name=op.f("fk_orders_showtime_id_showtimes"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_orders")),
        sa.UniqueConstraint("razorpay_order_id", name=op.f("uq_orders_razorpay_order_id")),
    )
    op.create_index("ix_orders_user_id_created_at", "orders", ["user_id", "created_at"])
    op.create_index("ix_orders_showtime_id_status", "orders", ["showtime_id", "status"])

    op.create_table(
        "order_seats",
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("seat_id", sa.Uuid(), nullable=False),
        sa.Column("tier_key", sa.Text(), nullable=False),
        sa.Column("price_paise", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name=op.f("fk_order_seats_order_id_orders"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["seat_id"],
            ["seats.id"],
            name=op.f("fk_order_seats_seat_id_seats"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("order_id", "seat_id", name=op.f("pk_order_seats")),
    )

    op.create_table(
        "tickets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("showtime_id", sa.Uuid(), nullable=False),
        sa.Column("seat_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("checked_in_at", sa.DateTime(timezone=True), nullable=True),
        _created_at(),
        sa.ForeignKeyConstraint(
            ["order_id"], ["orders.id"], name=op.f("fk_tickets_order_id_orders"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["showtime_id"],
            ["showtimes.id"],
            name=op.f("fk_tickets_showtime_id_showtimes"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["seat_id"], ["seats.id"], name=op.f("fk_tickets_seat_id_seats"), ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_tickets_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tickets")),
        # The final guard on confirm: a seat is sold once per showtime, whatever Redis said.
        sa.UniqueConstraint("showtime_id", "seat_id", name=op.f("uq_tickets_showtime_id_seat_id")),
    )
    op.create_index("ix_tickets_user_id", "tickets", ["user_id"])
    op.create_index("ix_tickets_order_id", "tickets", ["order_id"])

    op.create_table(
        "webhook_events",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_webhook_events")),
    )

    op.execute(SHOWTIME_FILL)


def downgrade() -> None:
    op.execute("drop view if exists showtime_fill")
    op.drop_table("webhook_events")
    op.drop_index("ix_tickets_order_id", table_name="tickets")
    op.drop_index("ix_tickets_user_id", table_name="tickets")
    op.drop_table("tickets")
    op.drop_table("order_seats")
    op.drop_index("ix_orders_showtime_id_status", table_name="orders")
    op.drop_index("ix_orders_user_id_created_at", table_name="orders")
    op.drop_table("orders")
    op.drop_table("price_tiers")
    op.drop_index("ix_showtimes_venue_id_starts_at", table_name="showtimes")
    op.drop_index("ix_showtimes_event_id_starts_at", table_name="showtimes")
    op.drop_index("ix_showtimes_starts_at", table_name="showtimes")
    op.drop_table("showtimes")
    op.drop_index("ix_events_status_type", table_name="events")
    op.drop_table("events")
    op.drop_index("ix_seats_venue_id", table_name="seats")
    op.drop_table("seats")
    op.drop_index("ix_venues_organiser_id", table_name="venues")
    op.drop_table("venues")
    op.drop_index("ix_sessions_user_id", table_name="sessions")
    op.drop_table("sessions")
    op.drop_table("users")
    bind = op.get_bind()
    for name in reversed(list(ENUMS)):
        _enum(name).drop(bind)
