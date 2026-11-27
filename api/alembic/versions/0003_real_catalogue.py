"""Real films (the Bollywood + Hollywood catalogue): CBFC's age-banded U/A certificates, and a
film may be listed before it is certified or its runtime is announced (both columns nullable).

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-27
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NEW_CERTS = ("UA 7+", "UA 13+", "UA 16+")


def upgrade() -> None:
    # ALTER TYPE … ADD VALUE can't be used in the transaction that adds it; commit it first.
    with op.get_context().autocommit_block():
        after = "UA"
        for value in NEW_CERTS:
            op.execute(f"alter type cert add value if not exists '{value}' after '{after}'")
            after = value
    op.alter_column("films", "cert", nullable=True)
    op.alter_column("films", "runtime_min", nullable=True)


def downgrade() -> None:
    # Postgres can't drop enum values: rebuild the type, folding the age bands back into UA.
    op.execute("update films set runtime_min = 150 where runtime_min is null")
    op.execute("alter type cert rename to cert_0003")
    op.execute("create type cert as enum ('U', 'UA', 'A')")
    op.execute(
        "alter table films alter column cert type cert using (case "
        "when cert is null or cert::text like 'UA%' then 'UA' else cert::text end)::cert"
    )
    op.execute("drop type cert_0003")
    op.alter_column("films", "cert", nullable=False)
    op.alter_column("films", "runtime_min", nullable=False)
