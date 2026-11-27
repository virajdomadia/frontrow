"""The hold engine (04 §4, 06 §B): atomic all-or-none seat holds in Redis.

Keys (the `{showtime}` braces are a Redis Cluster hash tag, so every key one script touches lives
in the same slot):

    fr:hold:{st}:{seat}   string = holder id, PX ttl       — the truth for "is this seat held"
    fr:holds:{st}         hash seat → "holder|net|expires_ms" — snapshot mirror, lazily cleaned
    fr:st:{st}:v          int, INCR on every hold / release / sale
    fr:rl:holds:{holder}  int, 60 s window                 — rate limit

A holder is the anonymous `fr_sid` cookie (or a bearer session's sid), so a visitor can hold
before signing in and keep the seats when they do.

One holder's seats in one showtime share a single deadline: the countdown starts at the first
successful hold (R4) and seats added later expire with it, not ten minutes after their own tap.

Caps, checked inside the same script so concurrent requests can't add up past them: 10 seats per
holder, and 20 per network (`net`, a hash of the client address) — two tabs of one person, but a
fresh cookie per request no longer buys more seats.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.errors import ApiError
from app.schemas.shows import HeldSeat

log = logging.getLogger(__name__)

MAX_SEATS = 10  # per booking (R3)
NET_SEATS = 2 * MAX_SEATS  # per network per show: the two-tabs demo, not a whole hall


def hold_key(showtime_id: uuid.UUID | str, seat_id: str) -> str:
    return f"fr:hold:{{{showtime_id}}}:{seat_id}"


def hash_key(showtime_id: uuid.UUID | str) -> str:
    return f"fr:holds:{{{showtime_id}}}"


def version_key(showtime_id: uuid.UUID | str) -> str:
    return f"fr:st:{{{showtime_id}}}:v"


# KEYS = hash, version, hold keys…; ARGV = holder, ttl_ms, now_ms, net, max per holder,
# max per net, seat ids…
# Seats already held by the same holder are re-granted (idempotent re-tap) and keep their TTL;
# fresh seats get the *remaining* TTL of the holder's existing seats, so all expire together.
# Returns {1, expires} | {0, taken seats} | {2} over the holder cap | {3} over the network cap.
ACQUIRE = """
local holder, ttl, now, net = ARGV[1], tonumber(ARGV[2]), tonumber(ARGV[3]), ARGV[4]
local taken, fresh = {}, {}
local left = ttl
for i = 3, #KEYS do
  local v = redis.call('GET', KEYS[i])
  if v == false then
    fresh[#fresh + 1] = i
  elseif v ~= holder then
    taken[#taken + 1] = ARGV[i + 4]
  else
    local p = redis.call('PTTL', KEYS[i])
    if p > 0 and p < left then left = p end
  end
end
if #taken > 0 then return {0, taken} end
local mine, ours, nmine, nours = {}, {}, 0, 0
local all = redis.call('HGETALL', KEYS[1])
for j = 1, #all, 2 do
  local h, n, e = string.match(all[j + 1], '^([^|]*)|(.*)|(%d+)$')
  if not h then h, e = string.match(all[j + 1], '^([^|]*)|(%d+)$') end
  if h and tonumber(e) > now then
    if h == holder then mine[all[j]] = true end
    if net ~= '' and n == net then ours[all[j]] = true end
  end
end
for i = 3, #KEYS do
  mine[ARGV[i + 4]] = true
  if net ~= '' then ours[ARGV[i + 4]] = true end
end
for _ in pairs(mine) do nmine = nmine + 1 end
for _ in pairs(ours) do nours = nours + 1 end
if nmine > tonumber(ARGV[5]) then return {2, 0} end
if nours > tonumber(ARGV[6]) then return {3, 0} end
local expires = now + left
for _, i in ipairs(fresh) do
  redis.call('SET', KEYS[i], holder, 'PX', left)
  redis.call('HSET', KEYS[1], ARGV[i + 4], holder .. '|' .. net .. '|' .. expires)
end
if #fresh > 0 then redis.call('INCR', KEYS[2]) end
return {1, expires}
"""

# KEYS = hash, version, hold keys…; ARGV = holder, seat ids… — compare-and-delete.
RELEASE = """
local holder = ARGV[1]
local n = 0
for i = 3, #KEYS do
  local seat = ARGV[i - 1]
  if redis.call('GET', KEYS[i]) == holder then
    redis.call('DEL', KEYS[i])
    n = n + 1
  end
  local h = redis.call('HGET', KEYS[1], seat)
  if h and string.sub(h, 1, #holder + 1) == holder .. '|' then
    redis.call('HDEL', KEYS[1], seat)
  end
end
if n > 0 then redis.call('INCR', KEYS[2]) end
return n
"""

# KEYS = hash, version, hold keys…; ARGV = seat ids… — a sale: the seat is gone for everyone.
CLEAR = """
for i = 3, #KEYS do
  redis.call('DEL', KEYS[i])
  redis.call('HDEL', KEYS[1], ARGV[i - 2])
end
redis.call('INCR', KEYS[2])
return 1
"""

# KEYS = hash; ARGV = seat, value, seat, value… — drop mirror entries that are still the stale
# value we read (a fresh hold written in between is left alone).
PRUNE = """
local n = 0
for i = 1, #ARGV, 2 do
  if redis.call('HGET', KEYS[1], ARGV[i]) == ARGV[i + 1] then
    redis.call('HDEL', KEYS[1], ARGV[i])
    n = n + 1
  end
end
return n
"""


def _ms(t: datetime) -> int:
    return int(t.timestamp() * 1000)


def _at(ms: int) -> datetime:
    return datetime.fromtimestamp(ms / 1000, tz=UTC)


@dataclass
class Holds:
    """Live holds for one showtime: `others` = someone else's, `mine` = the caller's."""

    v: int = 0
    others: list[HeldSeat] = field(default_factory=list)
    mine: list[str] = field(default_factory=list)
    mine_expires_at: datetime | None = None


@dataclass
class Granted:
    expires_at: datetime
    held: list[str]


def _unavailable(e: Exception) -> ApiError:
    log.warning("redis unavailable: %s", e)
    return ApiError("unavailable", "Seat holds are unavailable right now. Try again shortly.")


async def rate_limit(redis: Redis, holder: str, per_minute: int) -> None:
    """`per_minute` calls per `holder` (any key: a holder, `ip:…`, `demo:…`), else 429."""
    key = f"fr:rl:holds:{holder}"
    try:
        async with redis.pipeline(transaction=True) as pipe:
            pipe.incr(key)
            pipe.expire(key, 60, nx=True)
            count, _ = await pipe.execute()
    except RedisError as e:
        raise _unavailable(e) from e
    if int(count) > per_minute:
        raise ApiError(
            "rate_limited",
            "Too many tries in a minute. Wait a moment and try again.",
            status=429,
        )


async def acquire(
    redis: Redis,
    showtime_id: uuid.UUID,
    holder: str,
    seat_ids: Sequence[str],
    *,
    ttl_seconds: int,
    now: datetime,
    net: str = "",
) -> Granted:
    """All of `seat_ids` for `holder`, or none: 409 `seat_taken` naming the seats someone else
    holds. Seats the holder already has are fine (re-tap). 422 `too_many_seats` past 10 for
    the holder; 429 `too_many_holds` past 20 for the network `net` ("" = not counted)."""
    keys = [hash_key(showtime_id), version_key(showtime_id)]
    keys += [hold_key(showtime_id, s) for s in seat_ids]
    try:
        result = await redis.eval(  # type: ignore[misc]
            ACQUIRE, len(keys), *keys, holder, ttl_seconds * 1000, _ms(now), net, MAX_SEATS,
            NET_SEATS, *seat_ids,
        )  # fmt: skip
    except RedisError as e:
        raise _unavailable(e) from e
    ok, payload = result[0], result[1]
    if int(ok) == 2:
        raise ApiError(
            "too_many_seats", f"Up to {MAX_SEATS} seats per booking", status=422,
            details={"max": MAX_SEATS},
        )  # fmt: skip
    if int(ok) == 3:
        raise ApiError(
            "too_many_holds",
            "Too many seats are held from your network for this show. Finish or release a "
            "booking first.",
            status=429,
        )
    if int(ok) == 0:
        taken = [str(s) for s in payload]
        raise ApiError(
            "seat_taken",
            "That seat was just taken" if len(taken) == 1 else "Those seats were just taken",
            status=409,
            details={"taken": taken},
        )
    return Granted(expires_at=_at(int(payload)), held=list(seat_ids))


async def release(
    redis: Redis, showtime_id: uuid.UUID, holder: str, seat_ids: Sequence[str]
) -> int:
    """Drop the holder's own holds on `seat_ids` (someone else's are untouched)."""
    if not seat_ids:
        return 0
    keys = [hash_key(showtime_id), version_key(showtime_id)]
    keys += [hold_key(showtime_id, s) for s in seat_ids]
    try:
        return int(await redis.eval(RELEASE, len(keys), *keys, holder, *seat_ids))  # type: ignore[misc]
    except RedisError as e:
        raise _unavailable(e) from e


async def clear_sold(redis: Redis | None, showtime_id: uuid.UUID, seat_ids: Iterable[str]) -> None:
    """After a sale commits: delete every hold on the sold seats and bump the version. Best
    effort — the sale is already safe in Postgres, and sold beats held on every read."""
    seats = list(seat_ids)
    if redis is None or not seats:
        return
    keys = [hash_key(showtime_id), version_key(showtime_id)]
    keys += [hold_key(showtime_id, s) for s in seats]
    try:
        await redis.eval(CLEAR, len(keys), *keys, *seats)  # type: ignore[misc]
    except RedisError as e:
        log.warning("could not clear holds after a sale on %s: %s", showtime_id, e)


async def owned(
    redis: Redis, showtime_id: uuid.UUID, holder: str, seat_ids: Sequence[str]
) -> tuple[list[str], datetime | None]:
    """Which of `seat_ids` are still held by `holder` (TTL keys, the truth), and when the
    earliest of them expires."""
    if not seat_ids:
        return [], None
    try:
        async with redis.pipeline(transaction=False) as pipe:
            for s in seat_ids:
                pipe.get(hold_key(showtime_id, s))
                pipe.pttl(hold_key(showtime_id, s))
            out = await pipe.execute()
    except RedisError as e:
        raise _unavailable(e) from e
    mine: list[str] = []
    left: int | None = None
    for i, s in enumerate(seat_ids):
        value, pttl = out[2 * i], out[2 * i + 1]
        if value == holder and int(pttl) > 0:
            mine.append(s)
            left = int(pttl) if left is None else min(left, int(pttl))
    expires = _at(_ms(datetime.now(UTC)) + left) if left is not None else None
    return mine, expires


async def snapshot(
    redis: Redis | None, showtime_id: uuid.UUID, holder: str | None, *, now: datetime
) -> Holds:
    """`HGETALL holds:{st}` + `GET st:{st}:v`, expired mirror entries dropped (and pruned).
    Without Redis — or with it down — there are no holds to show, and v stays 0."""
    if redis is None:
        return Holds()
    try:
        async with redis.pipeline(transaction=True) as pipe:
            pipe.hgetall(hash_key(showtime_id))
            pipe.get(version_key(showtime_id))
            entries, v = await pipe.execute()
    except RedisError as e:
        log.warning("redis unavailable for snapshot: %s", e)
        return Holds()
    now_ms = _ms(now)
    holds = Holds(v=int(v or 0))
    stale: list[str] = []
    mine_exp: int | None = None
    for seat, value in sorted(entries.items()):
        who, *_, exp = value.split("|")  # holder|net|expires (or holder|expires)
        try:
            exp_ms = int(exp)
        except ValueError:
            stale += [seat, value]
            continue
        if exp_ms <= now_ms:
            stale += [seat, value]
        elif holder is not None and who == holder:
            holds.mine.append(seat)
            mine_exp = exp_ms if mine_exp is None else min(mine_exp, exp_ms)
        else:
            holds.others.append(HeldSeat(seat_id=seat, expires_at=_at(exp_ms)))
    if mine_exp is not None:
        holds.mine_expires_at = _at(mine_exp)
    if stale:
        try:
            await redis.eval(PRUNE, 1, hash_key(showtime_id), *stale)  # type: ignore[misc]
        except RedisError as e:
            log.warning("could not prune expired holds: %s", e)
    return holds


async def held_counts(
    redis: Redis | None, showtime_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, int]:
    """`HLEN holds:{st}` per showtime for the fill badge (F3). Lazily-pruned entries can count
    for a moment after expiry; the badge is a hint, never a guard. No Redis → zeros."""
    if redis is None or not showtime_ids:
        return {}
    try:
        async with redis.pipeline(transaction=False) as pipe:
            for st in showtime_ids:
                pipe.hlen(hash_key(st))
            counts = await pipe.execute()
    except RedisError as e:
        log.warning("redis unavailable for hold counts: %s", e)
        return {}
    return {st: int(n) for st, n in zip(showtime_ids, counts, strict=True)}
