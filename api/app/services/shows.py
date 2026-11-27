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

import asyncio
import hashlib
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import anyio
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import ApiError
from app.models import BlockedSeat, Business, Cinema, Film, Screen, Seat, Show, ShowPrice, Ticket
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


async def blocked_seats(db: AsyncSession, show_id: uuid.UUID) -> list[str]:
    return [
        str(s)
        for s in await db.scalars(select(BlockedSeat.seat_id).where(BlockedSeat.show_id == show_id))
    ]


async def taken_seats(db: AsyncSession, show_id: uuid.UUID) -> tuple[list[str], list[str]]:
    """(sold, blocked): every seat nobody can hold or buy."""
    return await sold_seats(db, show_id), await blocked_seats(db, show_id)


async def show_lock(db: AsyncSession, show_id: uuid.UUID) -> None:
    """Serialise the writes that decide who has a seat (a sale's tickets, an owner's block, a
    counter sale) per show, until the transaction ends. Holds stay lock-free in Redis."""
    await db.execute(select(func.pg_advisory_xact_lock(func.hashtextextended(str(show_id), 0))))


def state_of(
    sold: list[str], live: holds.Holds, now: datetime, blocked: list[str] | None = None
) -> SeatState:
    gone = set(sold) | set(blocked or [])
    return SeatState(
        v=live.v,
        server_time=now,
        sold=sold,
        blocked=blocked or [],
        held=[h for h in live.others if h.seat_id not in gone],  # sold / blocked beat held
        mine=[m for m in live.mine if m not in gone],
        mine_expires_at=live.mine_expires_at,
    )


async def seat_state(
    db: AsyncSession,
    show_id: str,
    *,
    redis: Redis | None,
    holder: str | None,
    now: datetime,
) -> SeatState:
    show, _, _, _ = await load(db, show_id, now)
    sold, blocked = await taken_seats(db, show.id)
    return state_of(sold, await holds.snapshot(redis, show.id, holder, now=now), now, blocked)


PING_SECONDS = 15.0  # an SSE comment keeps idle proxies from closing the stream


async def live_seats(
    redis: Redis,
    show_id: uuid.UUID | str,
    holder: str | None,
    reload_sold: Callable[[], Awaitable[tuple[list[str], list[str]]]],
    *,
    seconds: float,
    on_close: Callable[[], Awaitable[None]] | None = None,
) -> AsyncIterator[str]:
    """The seat map's live feed (L1), as SSE: a `snapshot` event (the `/seats` body) now and
    after every change, nothing in between but a ping comment. It sleeps on the show's pub/sub
    channel, waking for a publish (`holds.channel`) or the next hold deadline (expiry bumps no
    version), so an idle map costs no Redis commands. Sold seats are read from Postgres once
    subscribed (a sale in between can't be missed) and again only on an "s" publish. Ends after
    `seconds`, inside the platform's function limit; the browser's EventSource reconnects and
    gets a fresh snapshot."""
    loop = asyncio.get_running_loop()
    end = loop.time() + seconds
    pubsub = redis.pubsub()
    try:
        await pubsub.subscribe(holds.channel(show_id))
        sold, blocked = await reload_sold()
        yield "retry: 2000\n\n"
        last = ""
        while True:
            now = datetime.now(UTC)
            live = await holds.snapshot(redis, show_id, holder, now=now)
            state = state_of(sold, live, now, blocked)
            same = state.model_dump_json(exclude={"server_time"})
            if same != last:
                last = same
                yield f"event: snapshot\nid: {state.v}\ndata: {state.model_dump_json()}\n\n"
            deadlines = [h.expires_at for h in state.held]
            if state.mine_expires_at:
                deadlines.append(state.mine_expires_at)
            due = min(deadlines) if deadlines else None
            while True:
                left = end - loop.time()
                if left <= 0:
                    return
                wait = min(PING_SECONDS, left)
                if due is not None:
                    wait = min(wait, max((due - datetime.now(UTC)).total_seconds(), 0) + 0.05)
                msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=wait)
                if msg is None:
                    if due is not None and datetime.now(UTC) >= due:
                        break  # a hold lapsed: re-read
                    yield ": ping\n\n"
                    continue
                kinds = {msg["data"]}
                while msg := await pubsub.get_message(ignore_subscribe_messages=True, timeout=0):
                    kinds.add(msg["data"])  # a burst of changes → one snapshot
                if "x" in kinds:
                    yield "event: closed\ndata: {}\n\n"
                    return
                if "s" in kinds:
                    sold, blocked = await reload_sold()
                break
    except RedisError:
        return  # the browser reconnects, or falls back to polling
    finally:
        # A disconnect cancels the generator: shield the cleanup so the connection goes back
        # to the pool and the stream's slot is given back.
        with anyio.CancelScope(shield=True):
            await pubsub.aclose()
            if on_close is not None:
                await on_close()


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


def net_of(ip: str | None) -> str:
    """The caller's network as an opaque key ("" when unknown) — limits count per network."""
    return hashlib.sha256(ip.encode()).hexdigest()[:16] if ip else ""


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
    net = net_of(ip)
    if net:  # rotating the cookie doesn't reset this one
        await holds.rate_limit(redis, f"ip:{net}", 2 * per_minute)

    sold, blocked = await taken_seats(db, show.id)
    gone = (set(sold) | set(blocked)) & set(ids)
    if gone:
        raise ApiError(
            "seat_taken",
            "That seat isn't available" if len(gone) == 1 else "Those seats aren't available",
            status=409,
            details={"taken": sorted(gone)},
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
