"""Counter sales (L4): an idempotency key on orders, so a box-office sale retried after a timeout
or a double tap is the same sale, never a second one.

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("idempotency_key", sa.Text(), nullable=True))
    op.create_unique_constraint(op.f("uq_orders_idempotency_key"), "orders", ["idempotency_key"])


def downgrade() -> None:
    op.drop_constraint(op.f("uq_orders_idempotency_key"), "orders", type_="unique")
    op.drop_column("orders", "idempotency_key")
