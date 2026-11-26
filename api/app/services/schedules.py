"""Show schedules → shows (B1, B9).

**Occurrences.** A schedule is days of the week × wall-clock times (IST) over a date range. A
show ends `runtime` after it starts; on one screen two shows may not overlap, counting a
cleaning gap after each.

**Lazy materialisation (B1: a catalogue that never empties, no cron).** Open-ended schedules
(`to_date` null — the seeded cinemas) are turned into shows on read, up to 14 days ahead, the
first time someone looks after the horizon moved. One cheap query answers "anything to do?";
when there is, a transaction-scoped advisory lock lets one request do it while the others
carry on; `UNIQUE (screen_id, starts_at)` makes a race harmless. Owner schedules are bounded
and materialised at once (`services/owner.py`).

**Seeded sales.** A seeded schedule carries `seed_fill`; each show it materialises gets that
share of seats sold to fictional bookers in 1–4-seat orders, scattered the way a real hall
fills, so the demo never shows a row of empty halls. Real owners' schedules never do this.
"""

from __future__ import annotations

import hashlib
import logging
import random
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import delete, func, insert, or_, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Film, Order, OrderSeat, Screen, Show, ShowPrice, ShowSchedule, Ticket, User
from app.models.enums import OrderStatus, ShowStatus

log = logging.getLogger(__name__)

IST = ZoneInfo("Asia/Kolkata")
HORIZON_DAYS = 14
CLEANING_GAP = timedelta(minutes=15)
FEE_PAISE = 3000  # ₹30 convenience fee per ticket (R6); orders use the same constant
BOOKER_DOMAIN = "@bookers.frontrow.demo"
_LOCK = 72_011_402  # pg advisory lock id for materialisation


def ist_today(now: datetime) -> date:
    return now.astimezone(IST).date()


def at_ist(day: date, t: time) -> datetime:
    return datetime.combine(day, t, tzinfo=IST).astimezone(UTC)


def occurrences(
    days_of_week: Iterable[int], times: Iterable[time], start: date, end: date
) -> list[datetime]:
    """Every start (UTC) on `days_of_week` (0 = Monday) × `times` (IST) from `start` to `end`
    inclusive, in order."""
    days = set(days_of_week)
    clock = sorted(set(times))
    out: list[datetime] = []
    day = start
    while day <= end:
        if day.weekday() in days:
            out.extend(at_ist(day, t) for t in clock)
        day += timedelta(days=1)
    return out


def ends(starts_at: datetime, runtime_min: int) -> datetime:
    return starts_at + timedelta(minutes=runtime_min)


def clashes(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> bool:
    """Two shows on one screen overlap once each is padded with the cleaning gap."""
    return a_start < b_end + CLEANING_GAP and b_start < a_end + CLEANING_GAP


# --- materialise ----------------------------------------------------------------------------------


def _target(today: date) -> date:
    return today + timedelta(days=HORIZON_DAYS - 1)


async def materialise(db: AsyncSession, *, now: datetime) -> int:
    """Make sure every open-ended schedule has its shows up to the horizon. Returns the number
    of shows created (0 when there was nothing to do or another request is doing it)."""
    today = ist_today(now)
    target = _target(today)
    due_filter = (
        ShowSchedule.to_date.is_(None),
        or_(ShowSchedule.materialised_until.is_(None), ShowSchedule.materialised_until < target),
    )
    if await db.scalar(select(func.count()).select_from(ShowSchedule).where(*due_filter)) == 0:
        return 0
    got = await db.scalar(text("select pg_try_advisory_xact_lock(:k)"), {"k": _LOCK})
    if not got:
        await db.rollback()
        return 0
    schedules = list(await db.scalars(select(ShowSchedule).where(*due_filter)))
    created = 0
    bookers = await booker_ids(db)
    for schedule in schedules:
        start = max(schedule.from_date, today)
        if schedule.materialised_until is not None:
            start = max(start, schedule.materialised_until + timedelta(days=1))
        created += await materialise_schedule(db, schedule, start, target, now=now, bookers=bookers)
        schedule.materialised_until = target
    # Seeded sales for shows over two days ago have done their job; drop them so the free
    # database doesn't grow by a few thousand rows a day. Real customers' orders are untouched.
    await db.execute(
        delete(Order).where(
            Order.user_id.in_(select(User.id).where(User.email.like(f"%{BOOKER_DOMAIN}"))),
            Order.show_id.in_(select(Show.id).where(Show.ends_at < now - timedelta(days=2))),
        )
    )
    await db.commit()
    if created:
        log.info("materialised %d shows up to %s", created, target)
    return created


async def materialise_schedule(
    db: AsyncSession,
    schedule: ShowSchedule,
    start: date,
    end: date,
    *,
    now: datetime,
    bookers: list[uuid.UUID] | None = None,
) -> int:
    """Insert the schedule's shows from `start` to `end` (skipping ones in the past or already
    there) with their prices — and, for a seeded schedule, scattered sales."""
    if start > end:
        return 0
    film = await db.get(Film, schedule.film_id)
    screen = await db.get(Screen, schedule.screen_id)
    assert film is not None and screen is not None
    created = 0
    for starts_at in occurrences(schedule.days_of_week, schedule.times, start, end):
        if starts_at <= now:
            continue
        show_id = await db.scalar(
            pg_insert(Show)
            .values(
                id=uuid.uuid4(),
                schedule_id=schedule.id,
                screen_id=screen.id,
                film_id=film.id,
                language=schedule.language,
                format=schedule.format,
                starts_at=starts_at,
                ends_at=ends(starts_at, film.runtime_min),
                status=ShowStatus.SCHEDULED,
            )
            .on_conflict_do_nothing(index_elements=["screen_id", "starts_at"])
            .returning(Show.id)
        )
        if show_id is None:
            continue
        await db.execute(
            insert(ShowPrice),
            [
                {"show_id": show_id, "tier_key": k, "price_paise": int(p)}
                for k, p in schedule.prices.items()
            ],
        )
        created += 1
        if schedule.seed_fill and bookers:
            rng = random.Random(hashlib.sha256(f"{screen.id}{starts_at}".encode()).digest())
            # Sooner shows are busier; the weekend busiest. ±30 % so halls differ.
            days_out = (starts_at - now).total_seconds() / 86400
            soon = 1.0 if days_out < 2 else 0.75 if days_out < 5 else 0.4
            weekend = 1.25 if starts_at.astimezone(IST).weekday() >= 4 else 1.0
            fill = min(schedule.seed_fill * soon * weekend * rng.uniform(0.7, 1.3), 0.97)
            await sell_scattered(db, show_id, screen, schedule.prices, fill, bookers, rng)
    return created


async def booker_ids(db: AsyncSession) -> list[uuid.UUID]:
    return list(
        await db.scalars(
            select(User.id).where(User.email.like(f"%{BOOKER_DOMAIN}")).order_by(User.email)
        )
    )


@dataclass
class _Batch:
    """Paid orders for one show, inserted in three bulk statements."""

    show_id: uuid.UUID

    def __post_init__(self) -> None:
        self.orders: list[dict[str, Any]] = []
        self.order_seats: list[dict[str, Any]] = []
        self.tickets: list[dict[str, Any]] = []

    def order(
        self,
        seat_ids: list[str],
        tier: str,
        price: int,
        user_id: uuid.UUID,
        paid_at: datetime,
        method: str = "UPI",
    ) -> uuid.UUID:
        order_id = uuid.uuid4()
        self.orders.append(
            {
                "id": order_id,
                "user_id": user_id,
                "sid": f"seed-{order_id.hex[:12]}",
                "show_id": self.show_id,
                "status": OrderStatus.PAID,
                "subtotal_paise": price * len(seat_ids),
                "fee_paise": FEE_PAISE * len(seat_ids),
                "total_paise": (price + FEE_PAISE) * len(seat_ids),
                "payment_method": method,
                "paid_at": paid_at,
            }
        )
        for seat_id in seat_ids:
            self.order_seats.append(
                {"order_id": order_id, "seat_id": uuid.UUID(seat_id), "tier_key": tier,
                 "price_paise": price}
            )  # fmt: skip
            self.tickets.append(
                {"id": uuid.uuid4(), "order_id": order_id, "show_id": self.show_id,
                 "seat_id": uuid.UUID(seat_id), "user_id": user_id}
            )  # fmt: skip
        return order_id

    async def insert(self, db: AsyncSession) -> None:
        if self.orders:
            await db.execute(insert(Order), self.orders)
            await db.execute(insert(OrderSeat), self.order_seats)
            await db.execute(insert(Ticket), self.tickets)


async def sell_scattered(
    db: AsyncSession,
    show_id: uuid.UUID,
    screen: Screen,
    prices: dict[str, Any],
    fill: float,
    bookers: list[uuid.UUID],
    rng: random.Random,
    *,
    reserved: frozenset[str] = frozenset(),
) -> int:
    """Paid orders of 1–4 adjacent seats until `fill` of the screen is sold, at least one seat
    left free. Pass 1 takes runs with gaps between them; later passes fill what's left, so a
    90 % show ends with a few singles free, the way a near-sold-out hall looks."""
    on_sale = {k for k in prices}
    target = min(int(screen.seat_count * fill), screen.seat_count - 1 - len(reserved))
    remaining: list[tuple[str, list[str]]] = []
    for section in screen.layout["sections"]:
        if section["tier"] not in on_sale:
            continue
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
    batch = _Batch(show_id)
    sold = 0
    gapped = True
    paid_at = datetime.now(UTC) - timedelta(hours=rng.randint(2, 60))
    while sold < target and any(seat_ids for _, seat_ids in remaining):
        for tier, seat_ids in remaining:
            if sold >= target:
                break
            cursor = rng.randrange(0, 3) if gapped else 0
            skipped: list[str] = seat_ids[:cursor]
            while cursor < len(seat_ids) and sold < target:
                size = min(rng.choice([1, 2, 2, 3, 4]), target - sold, len(seat_ids) - cursor)
                run = seat_ids[cursor : cursor + size]
                batch.order(run, tier, int(prices[tier]), rng.choice(bookers), paid_at)
                sold += size
                gap = rng.randrange(1, 4) if gapped else 0
                skipped += seat_ids[cursor + size : cursor + size + gap]
                cursor += size + gap
            seat_ids[:] = skipped + seat_ids[cursor:]
        gapped = False
    await batch.insert(db)
    return sold


# --- overlap --------------------------------------------------------------------------------------


@dataclass
class Busy:
    starts_at: datetime
    ends_at: datetime
    film_title: str


async def busy_on_screen(
    db: AsyncSession, screen_id: uuid.UUID, start: date, end: date
) -> list[Busy]:
    """Everything that occupies the screen between `start` and `end` (IST days): scheduled
    shows, plus the not-yet-materialised future of open-ended schedules."""
    lo, hi = at_ist(start, time.min), at_ist(end + timedelta(days=1), time.min)
    rows = await db.execute(
        select(Show.starts_at, Show.ends_at, Film.title)
        .join(Film, Film.id == Show.film_id)
        .where(
            Show.screen_id == screen_id,
            Show.status == ShowStatus.SCHEDULED,
            Show.ends_at + CLEANING_GAP > lo,
            Show.starts_at < hi,
        )
    )
    busy = [Busy(s, e, t) for s, e, t in rows.tuples()]
    lazy = await db.execute(
        select(ShowSchedule, Film)
        .join(Film, Film.id == ShowSchedule.film_id)
        .where(ShowSchedule.screen_id == screen_id, ShowSchedule.to_date.is_(None))
    )
    for schedule, film in lazy.tuples():
        first = max(start, schedule.from_date)
        if schedule.materialised_until is not None:
            first = max(first, schedule.materialised_until + timedelta(days=1))
        for s in occurrences(schedule.days_of_week, schedule.times, first, end):
            busy.append(Busy(s, ends(s, film.runtime_min), film.title))
    return busy
