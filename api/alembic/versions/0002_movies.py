"""Movies-only marketplace (re-plan B1, 06 §A): events/venues/showtimes → films, businesses,
cinemas, screens, show schedules, shows; email-code users (no passwords; a staff flag instead of
an organiser role); film requests; orders/tickets keyed on shows.

The S2/F tables only ever held seeded demo data, so this revision drops them (0001's own
downgrade) and builds the new model; `python -m app.seed` refills it. Downgrading drops the new
model and re-runs 0001's upgrade.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-26
"""

import importlib.util
from collections.abc import Sequence
from pathlib import Path
from types import ModuleType

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ENUMS = {
    "session_kind": ("web", "mobile"),
    "cert": ("U", "UA", "A"),
    "film_status": ("coming_soon", "now_showing", "ended"),
    "business_status": ("pending", "verified", "rejected", "suspended"),
    "layout_template": ("grid", "stalls_balcony"),
    "show_status": ("scheduled", "cancelled"),
    "order_status": ("pending", "paid", "expired", "refunded", "failed"),
    "order_channel": ("online", "counter"),
    "request_status": ("open", "added", "declined"),
}

# Sold seats per show (fill badges, owner lists). Held counts come from Redis, merged in the API.
SHOW_FILL = """
create view show_fill as
select s.id as show_id, sc.seat_count, count(t.id)::int as sold
from shows s
join screens sc on sc.id = s.screen_id
left join tickets t on t.show_id = s.id
group by s.id, sc.seat_count
"""


def _v1() -> ModuleType:
    path = Path(__file__).with_name("0001_v1.py")
    spec = importlib.util.spec_from_file_location("frontrow_migration_0001", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _enum(name: str) -> postgresql.ENUM:
    return postgresql.ENUM(*ENUMS[name], name=name, create_type=False)


def _created_at() -> sa.Column:
    return sa.Column(
        "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
    )


def _fk(table: str, col: str, ref: str, ondelete: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        [col], [f"{ref}.id"], name=op.f(f"fk_{table}_{col}_{ref}"), ondelete=ondelete
    )


def upgrade() -> None:
    _v1().downgrade()
    bind = op.get_bind()
    for name in ENUMS:
        _enum(name).create(bind)

    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("is_staff", sa.Boolean(), server_default=sa.false(), nullable=False),
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
        _fk("sessions", "user_id", "users", "CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sessions")),
    )
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])

    op.create_table(
        "businesses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("phone", sa.Text(), nullable=False),
        sa.Column("logo_url", sa.Text(), nullable=True),
        sa.Column("status", _enum("business_status"), server_default="pending", nullable=False),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        _created_at(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_businesses")),
        sa.UniqueConstraint("slug", name=op.f("uq_businesses_slug")),
    )
    op.create_table(
        "business_members",
        sa.Column("business_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.Text(), server_default="owner", nullable=False),
        _fk("business_members", "business_id", "businesses", "CASCADE"),
        _fk("business_members", "user_id", "users", "CASCADE"),
        sa.PrimaryKeyConstraint("business_id", "user_id", name=op.f("pk_business_members")),
    )
    op.create_index("ix_business_members_user_id", "business_members", ["user_id"])

    op.create_table(
        "films",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("synopsis", sa.Text(), nullable=False),
        sa.Column("cast_crew", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("runtime_min", sa.Integer(), nullable=False),
        sa.Column("cert", _enum("cert"), nullable=False),
        sa.Column("genres", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("languages", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("formats", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("poster_url", sa.Text(), nullable=False),
        sa.Column("banner_url", sa.Text(), nullable=True),
        sa.Column("trailer_url", sa.Text(), nullable=True),
        sa.Column("release_date", sa.Date(), nullable=False),
        sa.Column("status", _enum("film_status"), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        _created_at(),
        _fk("films", "created_by", "users", "SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_films")),
        sa.UniqueConstraint("slug", name=op.f("uq_films_slug")),
    )
    op.create_index("ix_films_status", "films", ["status"])
    op.create_table(
        "film_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("business_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("status", _enum("request_status"), server_default="open", nullable=False),
        sa.Column("film_id", sa.Uuid(), nullable=True),
        sa.Column("reply", sa.Text(), nullable=True),
        _created_at(),
        _fk("film_requests", "business_id", "businesses", "CASCADE"),
        _fk("film_requests", "film_id", "films", "SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_film_requests")),
    )
    op.create_index("ix_film_requests_status", "film_requests", ["status"])

    op.create_table(
        "cinemas",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("business_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("area", sa.Text(), nullable=False),
        sa.Column("address", sa.Text(), nullable=False),
        sa.Column("facilities", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("photo_url", sa.Text(), nullable=True),
        _created_at(),
        _fk("cinemas", "business_id", "businesses", "CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cinemas")),
    )
    op.create_index("ix_cinemas_business_id", "cinemas", ["business_id"])
    op.create_table(
        "screens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("cinema_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("template", _enum("layout_template"), nullable=False),
        sa.Column("knobs", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("layout", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("tiers", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("formats", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("seat_count", sa.Integer(), nullable=False),
        _created_at(),
        _fk("screens", "cinema_id", "cinemas", "CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_screens")),
    )
    op.create_index("ix_screens_cinema_id", "screens", ["cinema_id"])
    op.create_table(
        "seats",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("screen_id", sa.Uuid(), nullable=False),
        sa.Column("section_key", sa.Text(), nullable=False),
        sa.Column("row_label", sa.Text(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("tier_key", sa.Text(), nullable=False),
        sa.Column("x", sa.Integer(), nullable=False),
        sa.Column("y", sa.Integer(), nullable=False),
        _fk("seats", "screen_id", "screens", "CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_seats")),
        sa.UniqueConstraint(
            "screen_id",
            "section_key",
            "row_label",
            "number",
            name=op.f("uq_seats_screen_id_section_key_row_label_number"),
        ),
    )
    op.create_index("ix_seats_screen_id", "seats", ["screen_id"])

    op.create_table(
        "show_schedules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("screen_id", sa.Uuid(), nullable=False),
        sa.Column("film_id", sa.Uuid(), nullable=False),
        sa.Column("language", sa.Text(), nullable=False),
        sa.Column("format", sa.Text(), nullable=False),
        sa.Column("days_of_week", postgresql.ARRAY(sa.Integer()), nullable=False),
        sa.Column("times", postgresql.ARRAY(sa.Time()), nullable=False),
        sa.Column("from_date", sa.Date(), nullable=False),
        sa.Column("to_date", sa.Date(), nullable=True),
        sa.Column("prices", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("materialised_until", sa.Date(), nullable=True),
        sa.Column("seed_fill", sa.Float(), nullable=True),
        _created_at(),
        _fk("show_schedules", "screen_id", "screens", "CASCADE"),
        _fk("show_schedules", "film_id", "films", "CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_show_schedules")),
    )
    op.create_index("ix_show_schedules_screen_id", "show_schedules", ["screen_id"])
    op.create_table(
        "shows",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("schedule_id", sa.Uuid(), nullable=True),
        sa.Column("screen_id", sa.Uuid(), nullable=False),
        sa.Column("film_id", sa.Uuid(), nullable=False),
        sa.Column("language", sa.Text(), nullable=False),
        sa.Column("format", sa.Text(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", _enum("show_status"), server_default="scheduled", nullable=False),
        sa.Column("cancel_reason", sa.Text(), nullable=True),
        _created_at(),
        _fk("shows", "schedule_id", "show_schedules", "SET NULL"),
        _fk("shows", "screen_id", "screens", "RESTRICT"),
        _fk("shows", "film_id", "films", "RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_shows")),
        sa.UniqueConstraint("screen_id", "starts_at", name=op.f("uq_shows_screen_id_starts_at")),
    )
    op.create_index("ix_shows_film_id_starts_at", "shows", ["film_id", "starts_at"])
    op.create_index("ix_shows_starts_at", "shows", ["starts_at"])
    op.create_table(
        "show_prices",
        sa.Column("show_id", sa.Uuid(), nullable=False),
        sa.Column("tier_key", sa.Text(), nullable=False),
        sa.Column("price_paise", sa.Integer(), nullable=False),
        _fk("show_prices", "show_id", "shows", "CASCADE"),
        sa.PrimaryKeyConstraint("show_id", "tier_key", name=op.f("pk_show_prices")),
    )

    op.create_table(
        "orders",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("sid", sa.Text(), nullable=False),
        sa.Column("show_id", sa.Uuid(), nullable=False),
        sa.Column("channel", _enum("order_channel"), server_default="online", nullable=False),
        sa.Column("status", _enum("order_status"), nullable=False),
        sa.Column("subtotal_paise", sa.Integer(), nullable=False),
        sa.Column("fee_paise", sa.Integer(), nullable=False),
        sa.Column("total_paise", sa.Integer(), nullable=False),
        sa.Column("razorpay_order_id", sa.Text(), nullable=True),
        sa.Column("razorpay_payment_id", sa.Text(), nullable=True),
        sa.Column("refund_id", sa.Text(), nullable=True),
        sa.Column("refund_reason", sa.Text(), nullable=True),
        sa.Column("payment_method", sa.Text(), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        _created_at(),
        _fk("orders", "user_id", "users", "SET NULL"),
        _fk("orders", "show_id", "shows", "CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_orders")),
        sa.UniqueConstraint("razorpay_order_id", name=op.f("uq_orders_razorpay_order_id")),
    )
    op.create_index("ix_orders_user_id_created_at", "orders", ["user_id", "created_at"])
    op.create_index("ix_orders_show_id_status", "orders", ["show_id", "status"])
    op.create_table(
        "order_seats",
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("seat_id", sa.Uuid(), nullable=False),
        sa.Column("tier_key", sa.Text(), nullable=False),
        sa.Column("price_paise", sa.Integer(), nullable=False),
        _fk("order_seats", "order_id", "orders", "CASCADE"),
        _fk("order_seats", "seat_id", "seats", "RESTRICT"),
        sa.PrimaryKeyConstraint("order_id", "seat_id", name=op.f("pk_order_seats")),
    )
    op.create_table(
        "tickets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("show_id", sa.Uuid(), nullable=False),
        sa.Column("seat_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("checked_in_at", sa.DateTime(timezone=True), nullable=True),
        _created_at(),
        _fk("tickets", "order_id", "orders", "CASCADE"),
        _fk("tickets", "show_id", "shows", "CASCADE"),
        _fk("tickets", "seat_id", "seats", "RESTRICT"),
        _fk("tickets", "user_id", "users", "CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tickets")),
        sa.UniqueConstraint("show_id", "seat_id", name=op.f("uq_tickets_show_id_seat_id")),
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
    op.execute(SHOW_FILL)


def downgrade() -> None:
    op.execute("drop view if exists show_fill")
    for table in (
        "webhook_events",
        "tickets",
        "order_seats",
        "orders",
        "show_prices",
        "shows",
        "show_schedules",
        "seats",
        "screens",
        "cinemas",
        "film_requests",
        "films",
        "business_members",
        "businesses",
        "sessions",
        "users",
    ):
        op.drop_table(table)  # their indexes go with them
    bind = op.get_bind()
    for name in reversed(list(ENUMS)):
        _enum(name).drop(bind)
    _v1().upgrade()
