"""App factory. Vercel's FastAPI preset imports the module-level `app` from here."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import Settings, get_settings
from app.db import dispose_engine
from app.errors import install_error_handlers
from app.middleware import BlankQueryParamsMiddleware, RequestIdMiddleware
from app.routers import health


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # The engine is created lazily by the first session (app/db.py); only disposal lives here.
    try:
        yield
    finally:
        await dispose_engine()


def create_app(settings: Settings | None = None) -> FastAPI:
    """`settings` lets tests build an app that ignores the local .env."""
    settings = settings or get_settings()
    app = FastAPI(
        title="Frontrow API",
        version="0.1.0",
        docs_url="/docs",
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.settings = settings  # read by db.get_session

    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(BlankQueryParamsMiddleware)
    install_error_handlers(app)

    app.include_router(health.router)
    return app


app = create_app()
