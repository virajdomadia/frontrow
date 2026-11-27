"""Seat-map reads and hold writes (06 §C): show detail, the screen layout, the live seat state,
and `POST/DELETE /shows/{id}/holds`.

Sold seats come from `tickets` (Postgres is the truth for a sale); holds come from Redis
(`services/holds.py`). A hold request is checked against Postgres first — a sold seat is a 409
too — then taken all-or-none by one Lua script.

A show is public only when its business is verified, its film is now showing and it is inside
the catalogue's horizon — the same rule as the catalogue. One that has started or was cancelled is
closed: every read and write answers 410 `show_closed`, with enough in `details` for the web to
say so and link back to the film.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timedelta
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import ApiError
from app.models import Business, Cinema, Film, Screen, Seat, Show, ShowPrice, Ticket
from app.models.enums import BusinessStatus, FilmStatus, ShowStatus
from app.schemas.catalog import TierPrice
from app.schemas.shows import (
    HoldGranted,
    SeatState,
    ShowCinema,
    ShowDetail,
    ShowFilm,
    ShowScreen,
)
from app.services import holds, schedules
from app.services.catalog import fill_of
from app.services.schedules import FEE_PAISE


def parse_id(raw: str | uuid.UUID, what: str = "show") -> uuid.UUID:
    if isinstance(raw, uuid.UUID):
        return raw
    try:
        return uuid.UUID(raw)
    except ValueError as e:
        raise ApiError("not_found", f"No such {what}") from e


def _check_open(show: Show, film: Film, cinema: Cinema, now: datetime) -> None:
    cancelled = show.status == ShowStatus.CANCELLED
    if not cancelled and show.starts_at > now:
        return
    raise ApiError(
        "show_closed",
        "This show was cancelled" if cancelled else "This show has already started",
        status=410,
        details={
            "reason": "cancelled" if cancelled else "started",
            "starts_at": show.starts_at.isoformat(),
            "film_slug": film.slug,
            "film_title": film.title,
            "cinema_name": cinema.name,
        },
    )


Loaded = tuple[Show, Film, Screen, Cinema]


async def load(db: AsyncSession, show_id: str | uuid.UUID, now: datetime) -> Loaded:
    """A public, open show with its film, screen and cinema — else 404 / 410."""
    row = (
        await db.execute(
            select(Show, Film, Screen, Cinema)
            .join(Film, Film.id == Show.film_id)
            .join(Screen, Screen.id == Show.screen_id)
            .join(Cinema, Cinema.id == Screen.cinema_id)
            .join(Business, Business.id == Cinema.business_id)
            .where(
                Show.id == parse_id(show_id),
                Business.status == BusinessStatus.VERIFIED,
                Film.status == FilmStatus.NOW_SHOWING,
                Show.starts_at < now + timedelta(days=schedules.HORIZON_DAYS),
            )
        )
    ).one_or_none()
    if row is None:
        raise ApiError("not_found", "No such show")
    show, film, screen, cinema = row._tuple()
    _check_open(show, film, cinema, now)
    return show, film, screen, cinema


async def tier_prices(db: AsyncSession, show: Show, screen: Screen) -> list[TierPrice]:
    """The screen's tiers front to back with this show's prices. A tier without a price isn't
    on sale for this show, so it's left out and its seats render unavailable."""
    prices = {
        p.tier_key: p.price_paise
        for p in await db.scalars(select(ShowPrice).where(ShowPrice.show_id == show.id))
    }
    return [
        TierPrice(tier_key=t["key"], label=t["label"], price_paise=prices[t["key"]])
        for t in screen.tiers
        if t["key"] in prices
    ]


async def get_show(
    db: AsyncSession, show_id: str, *, now: datetime, redis: Redis | None = None
) -> ShowDetail:
    show, film, screen, cinema = await load(db, show_id, now)
    sold = (
        await db.scalar(select(func.count()).select_from(Ticket).where(Ticket.show_id == show.id))
        or 0
    )
    held = (await holds.held_counts(redis, [show.id])).get(show.id, 0)
    return ShowDetail(
        id=show.id,
        starts_at=show.starts_at,
        ends_at=show.ends_at,
        language=show.language,
        format=show.format,
        status=show.status.value,  # type: ignore[arg-type]
        film=ShowFilm(
            id=film.id,
            slug=film.slug,
            title=film.title,
            cert=film.cert.value if film.cert else None,  # type: ignore[arg-type]
            runtime_min=film.runtime_min,
            poster_url=film.poster_url,
            genres=list(film.genres),
        ),
        cinema=ShowCinema(id=cinema.id, name=cinema.name, area=cinema.area, address=cinema.address),
        screen=ShowScreen(
            id=screen.id,
            name=screen.name,
            template=screen.template.value,  # type: ignore[arg-type]
            seat_count=screen.seat_count,
        ),
        tiers=await tier_prices(db, show, screen),
        layout_url=f"/screens/{screen.id}/layout",
        fee_paise=FEE_PAISE,
        fill=fill_of(screen.seat_count, sold, held),  # type: ignore[arg-type]
        seats_left=max(screen.seat_count - sold - held, 0),
    )


async def get_layout(db: AsyncSession, screen_id: str) -> dict[str, Any]:
    layout = await db.scalar(
        select(Screen.layout).where(Screen.id == parse_id(screen_id, "screen"))
    )
    if layout is None:
        raise ApiError("not_found", "No such screen")
    return layout


async def sold_seats(db: AsyncSession, show_id: uuid.UUID) -> list[str]:
    return [
        str(s) for s in await db.scalars(select(Ticket.seat_id).where(Ticket.show_id == show_id))
    ]


async def seat_state(
    db: AsyncSession,
    show_id: str,
    *,
    redis: Redis | None,
    holder: str | None,
    now: datetime,
) -> SeatState:
    show, _, _, _ = await load(db, show_id, now)
    sold = await sold_seats(db, show.id)
    live = await holds.snapshot(redis, show.id, holder, now=now)
    sold_set = set(sold)
    return SeatState(
        v=live.v,
        server_time=now,
        sold=sold,
        held=[h for h in live.others if h.seat_id not in sold_set],  # sold beats held
        mine=[m for m in live.mine if m not in sold_set],
        mine_expires_at=live.mine_expires_at,
    )


async def check_seats(db: AsyncSession, show: Show, seat_ids: list[str]) -> list[str]:
    """Every id is a seat of this show's screen in a tier on sale; duplicates dropped."""
    ids: list[str] = []
    for raw in dict.fromkeys(seat_ids):
        try:
            ids.append(str(uuid.UUID(raw)))
        except ValueError as e:
            raise ApiError(
                "validation", "Unknown seat", details={"fields": {"seat_ids": raw}}
            ) from e
    on_sale = select(ShowPrice.tier_key).where(ShowPrice.show_id == show.id)
    found = {
        str(s)
        for s in await db.scalars(
            select(Seat.id).where(
                Seat.screen_id == show.screen_id,
                Seat.id.in_([uuid.UUID(i) for i in ids]),
                Seat.tier_key.in_(on_sale),
            )
        )
    }
    missing = [i for i in ids if i not in found]
    if missing:
        raise ApiError(
            "validation",
            "Some seats aren't on sale for this show",
            details={"fields": {"seat_ids": "not on sale"}, "seats": missing},
        )
    return ids


def _too_many() -> ApiError:
    return ApiError(
        "too_many_seats",
        f"Up to {holds.MAX_SEATS} seats per booking",
        status=422,
        details={"max": holds.MAX_SEATS},
    )


async def place_holds(
    db: AsyncSession,
    redis: Redis,
    show_id: str,
    seat_ids: list[str],
    *,
    holder: str,
    ip: str | None,
    ttl_seconds: int,
    per_minute: int,
    now: datetime,
) -> HoldGranted:
    """Hold the whole selection or nothing (R5). Sold seats → 409 like held ones. Capped per
    holder and per network (`holds.ACQUIRE`)."""
    show, _, _, _ = await load(db, show_id, now)
    if len(set(seat_ids)) > holds.MAX_SEATS:
        raise _too_many()
    ids = await check_seats(db, show, seat_ids)
    await holds.rate_limit(redis, holder, per_minute)
    net = hashlib.sha256(ip.encode()).hexdigest()[:16] if ip else ""
    if net:  # rotating the cookie doesn't reset this one
        await holds.rate_limit(redis, f"ip:{net}", 2 * per_minute)

    sold = set(await sold_seats(db, show.id)) & set(ids)
    if sold:
        raise ApiError(
            "seat_taken",
            "That seat was just sold" if len(sold) == 1 else "Those seats were just sold",
            status=409,
            details={"taken": sorted(sold)},
        )
    granted = await holds.acquire(
        redis, show.id, holder, ids, ttl_seconds=ttl_seconds, now=now, net=net
    )
    return HoldGranted(expires_at=granted.expires_at, held=granted.held)


async def drop_holds(redis: Redis, show_id: str, seat_ids: list[str], *, holder: str) -> int:
    """Release the holder's own holds on these seats. Works on a closed show too, so a stale
    tab can always let go."""
    sid = parse_id(show_id)
    ids = []
    for raw in dict.fromkeys(seat_ids):
        try:
            ids.append(str(uuid.UUID(raw)))
        except ValueError:
            continue
    return await holds.release(redis, sid, holder, ids)
