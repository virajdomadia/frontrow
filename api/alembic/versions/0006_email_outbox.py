"""Email outbox (L5): every v2 customer email (show cancelled, resent tickets) is recorded first
and sent after the money is settled, so an email can never fail a refund. Staff read it, and
see why each one was or wasn't sent (SMTP off, a demo address, a failure).

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "email_outbox",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("to_email", sa.Text(), nullable=False),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.Text(), server_default="queued", nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name=op.f("fk_email_outbox_order_id_orders"),
            ondelete="SET NULL",
        ),  # fmt: skip
        sa.PrimaryKeyConstraint("id", name=op.f("pk_email_outbox")),
        sa.CheckConstraint(
            "status in ('queued', 'sent', 'failed', 'not_sent', 'logged', 'skipped')",
            name=op.f("ck_email_outbox_status"),
        ),
    )
    op.create_index("ix_email_outbox_created_at", "email_outbox", ["created_at"])
    op.create_index("ix_email_outbox_status", "email_outbox", ["status"])


def downgrade() -> None:
    op.drop_index("ix_email_outbox_status", table_name="email_outbox")
    op.drop_index("ix_email_outbox_created_at", table_name="email_outbox")
    op.drop_table("email_outbox")
