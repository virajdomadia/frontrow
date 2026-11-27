"""Blocked seats (L3): an owner takes seats off sale for one show (broken, staff, guests).
Customers see them as unavailable; holds, orders and the confirm transaction all refuse them.

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "blocked_seats",
        sa.Column("show_id", sa.Uuid(), nullable=False),
        sa.Column("seat_id", sa.Uuid(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["show_id"],
            ["shows.id"],
            name=op.f("fk_blocked_seats_show_id_shows"),
            ondelete="CASCADE",
        ),  # fmt: skip
        sa.ForeignKeyConstraint(
            ["seat_id"],
            ["seats.id"],
            name=op.f("fk_blocked_seats_seat_id_seats"),
            ondelete="RESTRICT",
        ),  # fmt: skip
        sa.PrimaryKeyConstraint("show_id", "seat_id", name=op.f("pk_blocked_seats")),
        sa.CheckConstraint(
            "reason in ('broken', 'staff', 'guests')", name=op.f("ck_blocked_seats_reason")
        ),
    )


def downgrade() -> None:
    op.drop_table("blocked_seats")
