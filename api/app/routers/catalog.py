"""Public catalogue routes (06 §C): `/home`, `/films`, `/films/{slug}`, `/films/{slug}/shows`.
Cached at the edge for a minute (04 §9); the seat map routes are `no-store`."""

from datetime import UTC, date, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.redis import optional_redis
from app.schemas.catalog import FilmDetail, FilmList, FilmShows, Home
from app.services import catalog
from app.services.schedules import IST

router = APIRouter(tags=["catalogue"])

CACHE = "public, s-maxage=60, stale-while-revalidate=300"
Db = Annotated[AsyncSession, Depends(get_session)]
OptRedis = Annotated[Redis | None, Depends(optional_redis)]


def cache_until(until: datetime, now: datetime) -> str:
    """`CACHE`, cut short so no shared cache serves the response — fresh or stale — past
    `until` (a show is closed once it starts; "today" is another day after IST midnight)."""
    left = int((until - now).total_seconds())
    if left <= 0:
        return "no-store"
    fresh = min(60, left)
    return f"public, s-maxage={fresh}, stale-while-revalidate={min(300, left - fresh)}"


def next_ist_midnight(now: datetime) -> datetime:
    day = now.astimezone(IST).date() + timedelta(days=1)
    return datetime.combine(day, datetime.min.time(), tzinfo=IST)


@router.get("/home", response_model=Home)
async def home(response: Response, db: Db, redis: OptRedis) -> Home:
    response.headers["Cache-Control"] = CACHE
    return await catalog.home(db, now=datetime.now(UTC), redis=redis)


@router.get("/films", response_model=FilmList)
async def films(
    response: Response,
    db: Db,
    redis: OptRedis,
    q: Annotated[str | None, Query(max_length=60, description="Search by title or genre")] = None,
) -> FilmList:
    response.headers["Cache-Control"] = CACHE
    return await catalog.search(db, q, now=datetime.now(UTC), redis=redis)


@router.get("/films/{slug}", response_model=FilmDetail)
async def film(slug: str, response: Response, db: Db, redis: OptRedis) -> FilmDetail:
    response.headers["Cache-Control"] = CACHE
    return await catalog.film_detail(db, slug, now=datetime.now(UTC), redis=redis)


@router.get("/films/{slug}/shows", response_model=FilmShows)
async def film_shows(
    slug: str,
    response: Response,
    db: Db,
    redis: OptRedis,
    date: Annotated[date | None, Query(description="IST day; default the first with shows")] = None,  # noqa: B008
    language: Annotated[str | None, Query(max_length=30)] = None,
    format: Annotated[str | None, Query(max_length=10)] = None,
) -> FilmShows:
    now = datetime.now(UTC)
    response.headers["Cache-Control"] = cache_until(next_ist_midnight(now), now)
    return await catalog.film_shows(
        db, slug, day=date, language=language, format=format, now=now, redis=redis
    )
