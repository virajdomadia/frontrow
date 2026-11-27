"""Shared fixtures: a fresh app per test and an in-process httpx client, plus the DB harness.

`raise_app_exceptions=False` so unhandled errors reach the test as the 500 envelope (what a real
client sees) instead of a traceback out of the transport.

DB harness: tests marked `db` need `TEST_DATABASE_URL`. Once per session the schema is rebuilt
through Alembic (downgrade base → upgrade head, so the downgrade path is exercised too); before
every test all tables are truncated. Without the variable, `db` tests are skipped.

Redis harness: tests marked `redis` need `TEST_REDIS_URL` (a throwaway database — it is flushed
before every test). The app gets it as `REDIS_URL`, with a 2-second hold TTL so expiry tests are
quick; without the variable, `redis` tests are skipped and the app runs with no Redis.
"""

import os
from collections.abc import AsyncIterator, Iterator

import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app import db as db_module
from app.db import get_session
from app.main import create_app
from app.models import Base
from app.redis import close_redis, redis_for
from app.services import schedules
from tests.helpers import Outbox
from tests.settings import make_settings

API_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
TEST_REDIS_URL = os.environ.get("TEST_REDIS_URL")
TEST_HOLD_TTL = 2


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "db: needs TEST_DATABASE_URL (Postgres)")
    config.addinivalue_line("markers", "redis: needs TEST_REDIS_URL (a throwaway Redis db)")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    for marker, url in (("db", TEST_DATABASE_URL), ("redis", TEST_REDIS_URL)):
        if url:
            continue
        skip = pytest.mark.skip(reason=f"TEST_{marker.upper()}_URL not set")
        for item in items:
            if marker in item.keywords:
                item.add_marker(skip)


@pytest.fixture(autouse=True)
def short_horizon(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests materialise 7 days of shows, not 14 — the same code, half the rows to insert."""
    monkeypatch.setattr(schedules, "HORIZON_DAYS", 7)


@pytest.fixture
async def app() -> AsyncIterator[FastAPI]:
    # Pure defaults (tests/settings.py): no env, no .env.local — the DB stays off; Redis is the
    # throwaway test database when there is one, flushed first.
    overrides: dict[str, object] = {}
    if TEST_REDIS_URL:
        overrides.update(redis_url=TEST_REDIS_URL, hold_ttl_seconds=TEST_HOLD_TTL)
    app = create_app(settings=make_settings(**overrides))
    app.state.mailer = Outbox()  # sign-in codes and ticket emails land here
    redis = redis_for(app)
    if redis is not None:
        await redis.flushdb()
    yield app
    await close_redis(app)


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# --- DB harness ---------------------------------------------------------------------------------


@pytest.fixture(scope="session")
def migrated_database_url() -> Iterator[str]:
    """Rebuild the schema via Alembic once per session (sync: env.py owns its own event loop)."""
    assert TEST_DATABASE_URL  # `db` tests are skipped without it
    os.environ["ALEMBIC_URL"] = TEST_DATABASE_URL
    cfg = Config(os.path.join(API_DIR, "alembic.ini"))
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    yield TEST_DATABASE_URL


@pytest.fixture
async def db_engine(migrated_database_url: str) -> AsyncIterator[AsyncEngine]:
    # Per test: asyncpg connections are bound to the running loop, and pytest-asyncio gives each
    # test its own loop, so the engine (NullPool, nothing to reuse) lives with the test.
    engine = create_async_engine(migrated_database_url, poolclass=NullPool)
    tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
    async with engine.begin() as conn:
        await conn.execute(text(f"truncate table {tables} restart identity cascade"))
    yield engine
    await engine.dispose()


@pytest.fixture
async def db(db_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    async with async_sessionmaker(db_engine, expire_on_commit=False)() as session:
        yield session


@pytest.fixture
async def db_app(app: FastAPI, db_engine: AsyncEngine) -> AsyncIterator[FastAPI]:
    """The app wired to the test database (routes that use the `get_session` dependency)."""
    factory = async_sessionmaker(db_engine, expire_on_commit=False)

    async def override() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    app.dependency_overrides[get_session] = override
    app.state.session_factory = factory  # db.side_session
    try:
        yield app
    finally:
        app.dependency_overrides.pop(get_session, None)
        await db_module.dispose_engine()


@pytest.fixture
async def db_client(db_app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=db_app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
