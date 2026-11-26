"""Sign-in by email code (04 §8, R1): three doors, opaque sessions, per-business access.

**Codes.** `POST /auth/code` stores the HMAC of a random 6-digit code in Redis (`otp:{email}`,
10-minute life, 5 tries) and emails it; `POST /auth/verify` checks it. Limits: one code a minute
and five an hour per email, thirty an hour per network. The staff door answers exactly the same
whether or not the email belongs to staff — it just never sends a code to anyone else.

**Doors.** customer (`/sign-in`): a new email is asked for a name. business (`/business`): a new
email — or an existing customer with no business — registers one (status pending). staff
(`/staff`): seeded staff only. One email = one person: every account can book; business access
and the staff flag sit on top.

**Sessions.** A session token is 32 random bytes handed to the client once — the `fr_session`
cookie (web) or a bearer token (v4 app, `POST /auth/token`). Only its HMAC is stored.

**Holds** belong to a *holder* id, not a user: the anonymous `fr_sid` cookie (it survives
sign-in, and the session records it as `sid` — the "adoption"), or the bearer session's sid.

**Demo accounts** (`*@frontrow.demo`) sign in with one click and are never emailed. Demo staff
can look at everything and decide nothing.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import re
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

from fastapi import Depends, Request, Response
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.db import get_session
from app.errors import ApiError
from app.models import Business, BusinessMember, Session, User
from app.models.enums import BusinessStatus, SessionKind
from app.services.mail import Mailer, MailError, code_mail

log = logging.getLogger(__name__)

Door = Literal["customer", "business", "staff"]

SESSION_COOKIE = "fr_session"
SID_COOKIE = "fr_sid"
WEB_DAYS = 30
MOBILE_DAYS = 90
CODE_TRIES = 5
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
DEMO_DOMAIN = "@frontrow.demo"
DEMO_EMAILS = {
    "customer": "customer@frontrow.demo",
    "owner": "owner@frontrow.demo",
    "staff": "staff@frontrow.demo",
}
_DEV_SECRET = b"frontrow-dev-session-secret"
_warned = False


def _secret(settings: Settings) -> bytes:
    global _warned
    if settings.session_secret is not None:
        return settings.session_secret.get_secret_value().encode()
    if not _warned:
        log.warning("SESSION_SECRET is not set; using a development-only key")
        _warned = True
    return _DEV_SECRET


def token_id(settings: Settings, token: str) -> str:
    return hmac.new(_secret(settings), token.encode(), hashlib.sha256).hexdigest()


def new_sid() -> str:
    return secrets.token_urlsafe(18)


def is_demo(user: User) -> bool:
    return user.email.endswith(DEMO_DOMAIN)


def normalise_email(email: str) -> str:
    email = email.strip().lower()
    if not EMAIL_RE.match(email) or len(email) > 254:
        raise ApiError(
            "validation", "Enter a valid email address", details={"fields": {"email": "invalid"}}
        )
    return email


@dataclass
class Auth:
    user: User
    session: Session


# --- codes ----------------------------------------------------------------------------------------


def _code_key(email: str) -> str:
    return f"otp:{email}"


def _code_hash(settings: Settings, email: str, code: str) -> str:
    return hmac.new(_secret(settings), f"{email}:{code}".encode(), hashlib.sha256).hexdigest()


def _unavailable(e: Exception) -> ApiError:
    log.warning("redis unavailable for sign-in codes: %s", e)
    return ApiError("unavailable", "Sign-in is unavailable right now. Try again shortly.")


async def _limit(redis: Redis, email: str, ip: str | None) -> None:
    """1 a minute + 5 an hour per email, 30 an hour per network. Raises 429."""
    try:
        if not await redis.set(f"rl:otp:m:{email}", 1, ex=60, nx=True):
            raise ApiError(
                "rate_limited",
                "We just sent a code. Wait a minute before asking for another.",
                status=429,
                details={"retry_after": int(await redis.ttl(f"rl:otp:m:{email}") or 60)},
            )
        keys = [f"rl:otp:h:{email}"] + ([f"rl:otp:ip:{ip}"] if ip else [])
        async with redis.pipeline(transaction=True) as pipe:
            for k in keys:
                pipe.incr(k)
                pipe.expire(k, 3600, nx=True)
            out = await pipe.execute()
    except RedisError as e:
        raise _unavailable(e) from e
    per_email = int(out[0])
    per_ip = int(out[2]) if ip else 0
    if per_email > 5 or per_ip > 30:
        raise ApiError(
            "rate_limited",
            "Too many codes asked for. Try again in an hour.",
            status=429,
            details={"retry_after": 3600},
        )


async def request_code(
    db: AsyncSession,
    redis: Redis,
    mailer: Mailer | None,
    settings: Settings,
    *,
    email: str,
    door: Door,
    ip: str | None,
) -> None:
    email = normalise_email(email)
    if email.endswith(DEMO_DOMAIN):
        raise ApiError(
            "validation",
            "Demo accounts sign in with the demo buttons — no code needed.",
            details={"fields": {"email": "demo"}},
        )
    if mailer is None:
        raise ApiError(
            "email_unavailable",
            "Email sign-in isn't switched on for this site yet. Use a demo button to look around.",
            status=503,
        )
    await _limit(redis, email, ip)
    if door == "staff":
        staff = await db.scalar(select(User.is_staff).where(User.email == email))
        if not staff:
            return  # same answer as for a real staff email: no hint either way
    code = f"{secrets.randbelow(1_000_000):06d}"
    try:
        await redis.hset(_code_key(email), mapping={"h": _code_hash(settings, email, code), "t": 0})
        await redis.expire(_code_key(email), settings.code_ttl_seconds)
    except RedisError as e:
        raise _unavailable(e) from e
    try:
        await mailer.send(code_mail(email, code, settings.code_ttl_seconds // 60))
    except MailError as e:
        log.error("sign-in code email failed: %s", e)
        await redis.delete(_code_key(email))
        raise ApiError(
            "email_unavailable", "We couldn't send the email. Try again in a minute.", status=503
        ) from e


async def check_code(
    redis: Redis, settings: Settings, email: str, code: str, *, consume: bool
) -> None:
    """Raise 401 unless `code` is the live code for `email`. A wrong code uses up a try (five
    and it's gone); `consume=False` checks a right code without spending it (the name step)."""
    key = _code_key(email)
    try:
        stored = await redis.hgetall(key)
        if not stored:
            raise ApiError("code_invalid", "That code has expired. Ask for a new one.", status=401)
        if not hmac.compare_digest(str(stored.get("h", "")), _code_hash(settings, email, code)):
            tries = await redis.hincrby(key, "t", 1)
            if tries >= CODE_TRIES:
                await redis.delete(key)
                raise ApiError(
                    "code_invalid", "Too many wrong codes. Ask for a new one.", status=401
                )
            left = CODE_TRIES - tries
            raise ApiError(
                "code_invalid",
                f"That code isn't right. {left} {'try' if left == 1 else 'tries'} left.",
                status=401,
                details={"tries_left": left},
            )
        if consume:
            await redis.delete(key)
    except RedisError as e:
        raise _unavailable(e) from e


def slugify(text: str, fallback: str = "x") -> str:
    import unicodedata

    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60] or fallback


async def unique_business_slug(db: AsyncSession, name: str) -> str:
    base = slugify(name, "cinema")
    taken = set(await db.scalars(select(Business.slug).where(Business.slug.like(f"{base}%"))))
    if base not in taken:
        return base
    n = 2
    while f"{base}-{n}" in taken:
        n += 1
    return f"{base}-{n}"


async def memberships(db: AsyncSession, user: User) -> list[tuple[Business, str]]:
    rows = await db.execute(
        select(Business, BusinessMember.role)
        .join(BusinessMember, BusinessMember.business_id == Business.id)
        .where(BusinessMember.user_id == user.id)
        .order_by(Business.created_at)
    )
    return [(b, role) for b, role in rows.tuples()]


async def register_business(
    db: AsyncSession, user: User, *, name: str, phone: str, logo_url: str | None
) -> Business:
    business = Business(
        name=name.strip(),
        slug=await unique_business_slug(db, name),
        phone=phone.strip(),
        logo_url=logo_url,
        status=BusinessStatus.PENDING,
    )
    db.add(business)
    await db.flush()
    db.add(BusinessMember(business_id=business.id, user_id=user.id, role="owner"))
    await db.flush()
    return business


@dataclass
class BusinessDetails:
    name: str
    phone: str
    logo_url: str | None = None


async def verify(
    db: AsyncSession,
    redis: Redis,
    settings: Settings,
    *,
    email: str,
    code: str,
    door: Door,
    name: str | None,
    business: BusinessDetails | None,
) -> User:
    """Check the code and return the user to sign in, creating the account (and, at the
    business door, the business) on first use. Asks for what's missing with 422
    `name_required` / `business_required` without spending the code."""
    email = normalise_email(email)
    user = await db.scalar(select(User).where(User.email == email))
    if door == "staff" and (user is None or not user.is_staff):
        # Unreachable for a real staff member; a stranger never had a code sent.
        await check_code(redis, settings, email, code, consume=False)
        raise ApiError("code_invalid", "That code isn't right.", status=401)

    needs_name = user is None and not (name and name.strip())
    needs_business = (
        door == "business"
        and (user is None or not await memberships(db, user))
        and business is None
    )
    await check_code(redis, settings, email, code, consume=False)
    if needs_name or needs_business:
        missing = ["name"] if needs_name else []
        missing += ["business"] if needs_business else []
        raise ApiError(
            "business_required" if needs_business else "name_required",
            "Tell us about your business to finish registering"
            if needs_business
            else "Tell us your name to finish signing up",
            status=422,
            details={"missing": missing},
        )
    await check_code(redis, settings, email, code, consume=True)

    if user is None:
        assert name is not None
        user = User(email=email, name=name.strip()[:80])
        db.add(user)
        await db.flush()
    if door == "business" and business is not None and not await memberships(db, user):
        await register_business(
            db, user, name=business.name, phone=business.phone, logo_url=business.logo_url
        )
    return user


# --- sessions -------------------------------------------------------------------------------------


async def create_session(
    db: AsyncSession,
    settings: Settings,
    user: User,
    *,
    kind: SessionKind,
    sid: str | None,
    now: datetime,
) -> tuple[str, Session]:
    token = secrets.token_urlsafe(32)
    days = MOBILE_DAYS if kind == SessionKind.MOBILE else WEB_DAYS
    session = Session(
        id=token_id(settings, token),
        user_id=user.id,
        sid=sid or new_sid(),
        kind=kind,
        expires_at=now + timedelta(days=days),
    )
    db.add(session)
    await db.commit()
    return token, session


async def lookup(db: AsyncSession, settings: Settings, token: str, now: datetime) -> Auth | None:
    row = (
        await db.execute(
            select(Session, User)
            .join(User, User.id == Session.user_id)
            .where(Session.id == token_id(settings, token), Session.expires_at > now)
        )
    ).one_or_none()
    if row is None:
        return None
    session, user = row._tuple()
    return Auth(user=user, session=session)


async def revoke(db: AsyncSession, settings: Settings, token: str) -> None:
    await db.execute(delete(Session).where(Session.id == token_id(settings, token)))
    await db.commit()


# --- cookies --------------------------------------------------------------------------------------


def set_session_cookie(response: Response, settings: Settings, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=WEB_DAYS * 86400,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        path="/",
    )


def clear_session_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        SESSION_COOKIE, httponly=True, samesite="lax", secure=settings.cookie_secure, path="/"
    )


def set_sid_cookie(response: Response, settings: Settings, sid: str) -> None:
    response.set_cookie(
        SID_COOKIE,
        sid,
        max_age=WEB_DAYS * 86400,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        path="/",
    )


def client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for", "")
    first = forwarded.split(",")[0].strip()
    return first or (request.client.host if request.client else None)


# --- dependencies ---------------------------------------------------------------------------------


def _bearer(request: Request) -> str | None:
    header = request.headers.get("authorization", "")
    scheme, _, value = header.partition(" ")
    return value.strip() or None if scheme.lower() == "bearer" else None


async def optional_auth(
    request: Request, db: Annotated[AsyncSession, Depends(get_session)]
) -> Auth | None:
    """The signed-in user from a bearer token (app) or the session cookie (web), else None."""
    token = _bearer(request) or request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    settings: Settings = request.app.state.settings
    return await lookup(db, settings, token, datetime.now(UTC))


async def require_auth(auth: Annotated[Auth | None, Depends(optional_auth)]) -> Auth:
    if auth is None:
        raise ApiError("unauthorized", "Sign in to continue")
    return auth


async def require_staff(auth: Annotated[Auth, Depends(require_auth)]) -> Auth:
    if not auth.user.is_staff:
        raise ApiError("forbidden", "This page is for Frontrow staff")
    return auth


async def require_staff_writer(auth: Annotated[Auth, Depends(require_staff)]) -> Auth:
    """Staff who may decide. The demo staff account can look but not change anything."""
    if is_demo(auth.user):
        raise ApiError(
            "demo_read_only",
            "The demo staff account can look around but not make changes.",
            status=403,
        )
    return auth


@dataclass
class Owner:
    auth: Auth
    business: Business


async def require_owner(
    auth: Annotated[Auth, Depends(require_auth)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> Owner:
    """A member of a business. v1: one business per account — the first one."""
    found = await memberships(db, auth.user)
    if not found:
        raise ApiError(
            "forbidden", "Register your business first", details={"reason": "no_business"}
        )
    return Owner(auth=auth, business=found[0][0])


def holder_of(
    request: Request, response: Response, auth: Auth | None, *, create: bool
) -> str | None:
    """The id holds are keyed on. Bearer clients: their session's sid. Web: the `fr_sid`
    cookie — set here when missing and `create` (a first hold)."""
    if auth is not None and _bearer(request) and auth.session.sid:
        return auth.session.sid
    sid = request.cookies.get(SID_COOKIE)
    if sid:
        return sid
    if auth is not None and auth.session.sid:
        sid = auth.session.sid
    elif not create:
        return None
    else:
        sid = new_sid()
    set_sid_cookie(response, request.app.state.settings, sid)
    return sid
