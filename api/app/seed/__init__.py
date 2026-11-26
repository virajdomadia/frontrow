"""Seed the demo catalogue (R9): `uv run python -m app.seed [--url URL] [--reset]`.

Idempotent by construction — running it twice never duplicates anything:
- users are upserted by email;
- venues are looked up by (organiser, name) and only generated when missing, so seat ids stay
  stable across runs (holds and tickets key on them);
- events are upserted by slug;
- the demo organiser's showtimes are **replaced** every run (they are relative to "now"), which
  cascades their orders and tickets; sold seats are then re-scattered with a fixed RNG seed,
  and the demo customer's own bookings (`DEMO_BOOKINGS`, one already played) are re-made.
`--reset` also drops the organiser's venues first (use after changing knobs).
"""

import argparse
import asyncio
import random
import sys
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from argon2 import PasswordHasher
from sqlalchemy import delete, insert, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.config import get_settings
from app.db import asyncpg_url, make_engine
from app.models import Event, Order, OrderSeat, PriceTier, Showtime, Ticket, User, Venue
from app.models.enums import EventStatus, EventType, OrderStatus, ShowtimeStatus, UserRole
from app.seed import content
from app.seed.content import (
    DEMO_BOOKINGS,
    EVENTS,
    FEE_PAISE,
    SHOWTIMES,
    VENUES,
    EventSpec,
    VenueSpec,
)
from app.services.venues import create_venue

RNG_SEED = 42


class SeedReport(dict[str, int]):
    def __str__(self) -> str:
        return ", ".join(f"{k} {v}" for k, v in self.items())


async def seed(
    engine: AsyncEngine, *, now: datetime | None = None, reset: bool = False
) -> SeedReport:
    now = now or datetime.now(UTC)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        organiser, customer, bookers = await _users(db)
        if reset:
            # Showtimes first: showtimes.venue_id is ON DELETE RESTRICT, and their orders /
            # tickets still reference the seats.
            owned = select(Venue.id).where(Venue.organiser_id == organiser.id)
            await db.execute(delete(Showtime).where(Showtime.venue_id.in_(owned)))
            await db.execute(delete(Venue).where(Venue.organiser_id == organiser.id))
        venues = {spec.key: await _venue(db, organiser.id, spec) for spec in VENUES}
        specs = {spec.slug: spec for spec in EVENTS}
        events = {spec.slug: await _event(db, organiser.id, spec) for spec in EVENTS}
        await db.execute(
            delete(Showtime).where(Showtime.event_id.in_([e.id for e in events.values()]))
        )
        await db.flush()

        day0 = content.day_zero(now)
        rng = random.Random(RNG_SEED)
        tickets = 0
        for spec in SHOWTIMES:
            event, venue = events[spec.event], venues[spec.venue]
            showtime = Showtime(
                event_id=event.id,
                venue_id=venue.id,
                starts_at=content.starts_at(spec, day0),
                status=ShowtimeStatus.SCHEDULED,
            )
            db.add(showtime)
            await db.flush()
            tiers = _tiers_for(venue, specs[spec.event])
            db.add_all(
                PriceTier(showtime_id=showtime.id, tier_key=k, label=label, price_paise=p)
                for k, (label, p) in tiers.items()
            )
            demo = DEMO_BOOKINGS.get((spec.event, spec.day))
            reserved = _centre_seats(venue, *demo) if demo else []
            tickets += await _sell(
                db, showtime, venue, tiers, spec.fill, bookers, rng, reserved=set(reserved)
            )
            if demo:
                paid_at = min(now - timedelta(hours=3), showtime.starts_at - timedelta(days=2))
                batch = _Batch()
                batch.order(showtime, reserved, demo[0], tiers[demo[0]][1], customer, paid_at)
                await batch.insert(db)
                tickets += len(reserved)
        await db.commit()
    return SeedReport(
        users=2 + len(bookers), venues=len(venues), events=len(events), showtimes=len(SHOWTIMES),
        tickets=tickets,
    )  # fmt: skip


# --- users ----------------------------------------------------------------------------------------


async def _users(db: AsyncSession) -> tuple[User, User, list[User]]:
    hasher = PasswordHasher()
    demo_hash = hasher.hash(content.DEMO_PASSWORD)
    organiser = await _upsert_user(
        db, content.ORGANISER_EMAIL, "Orbit Cinemas", UserRole.ORGANISER, demo_hash
    )
    customer = await _upsert_user(
        db, content.CUSTOMER_EMAIL, "Demo customer", UserRole.CUSTOMER, demo_hash
    )
    # Bookers can never sign in: an unguessable password hashed once and shared.
    locked = hasher.hash(uuid.uuid4().hex)
    bookers = [
        await _upsert_user(
            db, f"booker-{i + 1:02d}@frontrow.demo", name, UserRole.CUSTOMER, locked, keep=True
        )
        for i, name in enumerate(content.BOOKER_NAMES[: content.BOOKER_COUNT])
    ]
    return organiser, customer, bookers


async def _upsert_user(
    db: AsyncSession,
    email: str,
    name: str,
    role: UserRole,
    password_hash: str,
    *,
    keep: bool = False,
) -> User:
    user = await db.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(email=email, name=name, role=role, password_hash=password_hash)
        db.add(user)
        await db.flush()
    elif not keep:
        user.name, user.role, user.password_hash = name, role, password_hash
    return user


# --- venues ---------------------------------------------------------------------------------------


async def _venue(db: AsyncSession, organiser_id: uuid.UUID, spec: VenueSpec) -> Venue:
    venue = await db.scalar(
        select(Venue).where(Venue.organiser_id == organiser_id, Venue.name == spec.name)
    )
    if venue is not None:
        venue.address, venue.photo_url = spec.address, spec.photo_url
        return venue
    return await create_venue(
        db, organiser_id, name=spec.name, address=spec.address, photo_url=spec.photo_url,
        knobs=spec.knobs,
    )  # fmt: skip


# --- events ---------------------------------------------------------------------------------------


async def _event(db: AsyncSession, organiser_id: uuid.UUID, spec: EventSpec) -> Event:
    event = await db.scalar(select(Event).where(Event.slug == spec.slug))
    if event is None:
        event = Event(organiser_id=organiser_id, slug=spec.slug)
        db.add(event)
    event.title = spec.title
    event.type = EventType(spec.type)
    event.genre = spec.genre
    event.duration_min = spec.duration_min
    event.rating = spec.rating
    event.synopsis = spec.synopsis
    event.cast_lineup = list(spec.cast_lineup)
    event.poster_url = spec.poster_url
    event.gallery_urls = list(spec.gallery_urls)
    event.status = EventStatus.LIVE
    await db.flush()
    return event


def _tiers_for(venue: Venue, event: EventSpec) -> dict[str, tuple[str, int]]:
    """`tier_key → (label, price_paise)` for every tier the venue's layout uses."""
    return {t["key"]: (t["label"], event.prices[t["key"]]) for t in venue.layout["tiers"]}


# --- sold seats -----------------------------------------------------------------------------------


async def _sell(
    db: AsyncSession,
    showtime: Showtime,
    venue: Venue,
    tiers: dict[str, tuple[str, int]],
    fill: float,
    bookers: list[User],
    rng: random.Random,
    *,
    reserved: set[str] = frozenset(),  # type: ignore[assignment]
) -> int:
    """Paid orders of 1–4 adjacent seats until `fill` of the venue is sold, at least one seat
    left free (R9). Pass 1 takes runs with gaps between them (scattered); later passes fill what
    is left, so a 90 % show ends with a few singles free, the way a near-sold-out hall looks."""
    target = min(int(venue.seat_count * fill), venue.seat_count - 1 - len(reserved))
    # Each row split into runs of seats around the reserved ones, so orders stay adjacent.
    remaining: list[tuple[str, list[str]]] = []
    for section in venue.layout["sections"]:
        for row in section["rows"]:
            run: list[str] = []
            for s in row["seats"]:
                if s["id"] in reserved:
                    if run:
                        remaining.append((section["tier"], run))
                    run = []
                else:
                    run.append(s["id"])
            if run:
                remaining.append((section["tier"], run))
    rng.shuffle(remaining)
    batch = _Batch()
    sold = 0
    gapped = True
    while sold < target and any(seat_ids for _, seat_ids in remaining):
        for tier, seat_ids in remaining:
            if sold >= target:
                break
            cursor = rng.randrange(0, 3) if gapped else 0
            skipped: list[str] = seat_ids[:cursor]  # the leading gap goes back into the pool
            while cursor < len(seat_ids) and sold < target:
                size = min(rng.choice([1, 2, 2, 3, 4]), target - sold, len(seat_ids) - cursor)
                run = seat_ids[cursor : cursor + size]
                batch.order(showtime, run, tier, tiers[tier][1], rng.choice(bookers))
                sold += size
                gap = rng.randrange(1, 4) if gapped else 0
                skipped += seat_ids[cursor + size : cursor + size + gap]
                cursor += size + gap
            seat_ids[:] = skipped + seat_ids[cursor:]
        gapped = False
    await batch.insert(db)
    return sold


def _centre_seats(venue: Venue, tier: str, count: int) -> list[str]:
    """`count` adjacent seats in the middle of the middle row of `tier`'s first section."""
    section = next(s for s in venue.layout["sections"] if s["tier"] == tier)
    row = section["rows"][len(section["rows"]) // 2]["seats"]
    start = max((len(row) - count) // 2, 0)
    return [s["id"] for s in row[start : start + count]]


class _Batch:
    """Rows for one showtime's paid orders, inserted in three bulk statements."""

    def __init__(self) -> None:
        self.orders: list[dict[str, Any]] = []
        self.order_seats: list[dict[str, Any]] = []
        self.tickets: list[dict[str, Any]] = []

    def order(
        self,
        showtime: Showtime,
        run: list[str],
        tier: str,
        price: int,
        booker: User,
        paid_at: datetime | None = None,
    ) -> None:
        order_id = uuid.uuid4()
        self.orders.append(
            {
                "id": order_id,
                "user_id": booker.id,
                "sid": f"seed-{order_id.hex[:12]}",
                "showtime_id": showtime.id,
                "status": OrderStatus.PAID,
                "subtotal_paise": price * len(run),
                "fee_paise": FEE_PAISE * len(run),
                "total_paise": (price + FEE_PAISE) * len(run),
                "paid_at": paid_at or datetime.now(UTC),
            }
        )
        for seat_id in run:
            self.order_seats.append(
                {
                    "order_id": order_id,
                    "seat_id": uuid.UUID(seat_id),
                    "tier_key": tier,
                    "price_paise": price,
                }
            )
            self.tickets.append(
                {
                    "id": uuid.uuid4(),
                    "order_id": order_id,
                    "showtime_id": showtime.id,
                    "seat_id": uuid.UUID(seat_id),
                    "user_id": booker.id,
                }
            )

    async def insert(self, db: AsyncSession) -> None:
        if self.orders:
            await db.execute(insert(Order), self.orders)
            await db.execute(insert(OrderSeat), self.order_seats)
            await db.execute(insert(Ticket), self.tickets)


# --- CLI ------------------------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])  # type: ignore[union-attr]
    parser.add_argument("--url", help="asyncpg URL; default DATABASE_URL from api/.env.local")
    parser.add_argument("--reset", action="store_true", help="drop the demo venues first")
    args = parser.parse_args(argv)
    url = args.url
    if not url:
        secret = get_settings().database_url
        if secret is None:
            raise SystemExit("Set DATABASE_URL (api/.env.local) or pass --url")
        url = secret.get_secret_value()

    async def run() -> SeedReport:
        engine = make_engine(asyncpg_url(url))
        try:
            return await seed(engine, reset=args.reset)
        finally:
            await engine.dispose()

    print(f"seeded: {asyncio.run(run())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
