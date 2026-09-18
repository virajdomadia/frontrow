"""The hand-written 0001_v1 migration must match the models, and the view must exist."""

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.models import Base

pytestmark = pytest.mark.db


async def test_migration_matches_models(db_engine: AsyncEngine) -> None:
    def diff(conn):  # type: ignore[no-untyped-def]
        ctx = MigrationContext.configure(conn, opts={"compare_server_default": True})
        return compare_metadata(ctx, Base.metadata)

    async with db_engine.connect() as conn:
        drift = await conn.run_sync(diff)
    assert drift == [], f"models and 0001_v1 disagree: {drift}"


async def test_showtime_fill_view_exists(db_engine: AsyncEngine) -> None:
    async with db_engine.connect() as conn:
        cols = await conn.execute(
            text(
                "select column_name from information_schema.columns "
                "where table_name = 'showtime_fill' order by ordinal_position"
            )
        )
    assert [c[0] for c in cols] == ["showtime_id", "seat_count", "sold"]
