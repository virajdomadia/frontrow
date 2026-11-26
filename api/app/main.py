"""App factory. Vercel's FastAPI preset imports the module-level `app` from here."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse

from app.config import Settings, get_settings
from app.db import dispose_engine
from app.errors import install_error_handlers
from app.middleware import BlankQueryParamsMiddleware, NoSniffMiddleware, RequestIdMiddleware
from app.redis import close_redis
from app.routers import auth, events, health, orders, organiser, showtimes

# Swagger UI from jsdelivr at an exact version, not FastAPI's floating `@5`: the docs page runs
# whatever that tag points at, so a release can't change (or break) it under us.
SWAGGER_UI = "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.34.1"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # The engine and the Redis client are created lazily on first use (app/db.py, app/redis.py);
    # only disposal lives here.
    try:
        yield
    finally:
        await close_redis(app)
        await dispose_engine()


def create_app(settings: Settings | None = None) -> FastAPI:
    """`settings` lets tests build an app that ignores the local .env."""
    settings = settings or get_settings()
    app = FastAPI(
        title="Frontrow API",
        version="0.1.0",
        docs_url=None,  # served below with a pinned Swagger UI
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.settings = settings  # read by db.get_session

    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(NoSniffMiddleware)
    app.add_middleware(BlankQueryParamsMiddleware)
    install_error_handlers(app)

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(events.router)
    app.include_router(showtimes.router)
    app.include_router(orders.router)
    app.include_router(organiser.router)

    @app.get("/docs", include_in_schema=False)
    async def docs() -> HTMLResponse:
        return get_swagger_ui_html(
            openapi_url=app.openapi_url or "/openapi.json",
            title=f"{app.title} - Swagger UI",
            swagger_js_url=f"{SWAGGER_UI}/swagger-ui-bundle.js",
            swagger_css_url=f"{SWAGGER_UI}/swagger-ui.css",
        )

    return app


app = create_app()
