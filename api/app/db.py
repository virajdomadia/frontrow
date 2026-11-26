"""Database engine + session dependency.

Engines are created lazily per database URL — the app must import and serve `/health` with no
`DATABASE_URL` at all (CI, tests) — and disposed by the lifespan. The dependency reads the URL
from the app's own `Settings` (`app.state.settings`), never from the process env behind the app's
back, so a test app with no URL stays offline even when the developer's `.env.local` has one.
"""

from collections.abc import AsyncIterator
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from fastapi import Request
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import Settings

_engines: dict[str, AsyncEngine] = {}


class DatabaseNotConfigured(RuntimeError):
    pass


def asyncpg_url(url: str) -> str:
    """Accept the URL exactly as Neon's dashboard hands it out
    (`postgresql://…?sslmode=require&channel_binding=require`) as well as a ready asyncpg URL.
    asyncpg takes `ssl=`, not libpq's `sslmode=`, and has no `channel_binding` option."""
    parts = urlsplit(url)
    scheme = "postgresql+asyncpg" if parts.scheme in ("postgres", "postgresql") else parts.scheme
    query = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        if key == "channel_binding":
            continue
        query.append(("ssl" if key == "sslmode" else key, value))
    return urlunsplit((scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def make_engine(url: str) -> AsyncEngine:
    """Neon's pooled endpoint closes idle connections, so `pool_pre_ping` re-validates before
    use; the pool stays small for a serverless function."""
    return create_async_engine(url, pool_pre_ping=True, pool_size=2, max_overflow=3)


def get_engine(settings: Settings) -> AsyncEngine:
    if settings.database_url is None:
        raise DatabaseNotConfigured("DATABASE_URL is not set")
    url = asyncpg_url(settings.database_url.get_secret_value())
    engine = _engines.get(url)
    if engine is None:
        engine = _engines[url] = make_engine(url)
    return engine


def session_factory(settings: Settings) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(settings), expire_on_commit=False)


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: one session per request, rolled back unless the service committed."""
    settings: Settings = request.app.state.settings
    async with session_factory(settings)() as session:
        yield session


async def dispose_engine() -> None:
    for engine in list(_engines.values()):
        await engine.dispose()
    _engines.clear()
