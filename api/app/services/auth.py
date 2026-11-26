"""Own session auth (04 §8): argon2 passwords, opaque session tokens, roles.

A session token is 32 random bytes handed to the client once — as the `fr_session` cookie (web)
or a bearer token (v4 app, `POST /auth/token`). Only its HMAC is stored (`sessions.id`), so a
database leak doesn't leak live sessions.

Holds belong to a *holder* id, not a user: the anonymous `fr_sid` cookie for the web (it
survives sign-in, and the session records it as `sid` — that is the "adoption"), or the bearer
session's own `sid` for the app.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import re
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Annotated

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Depends, Request, Response
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.db import get_session
from app.errors import ApiError
from app.models import Session, User
from app.models.enums import SessionKind, UserRole

log = logging.getLogger(__name__)

SESSION_COOKIE = "fr_session"
SID_COOKIE = "fr_sid"
WEB_DAYS = 30
MOBILE_DAYS = 90
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
DEMO_EMAILS = {"customer": "customer@frontrow.demo", "organiser": "organiser@frontrow.demo"}

_hasher = PasswordHasher()
# Verified against when the email is unknown, so a miss costs the same as a wrong password.
_DUMMY_HASH = _hasher.hash(secrets.token_hex(16))
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


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def normalise_email(email: str) -> str:
    email = email.strip().lower()
    if not EMAIL_RE.match(email):
        raise ApiError(
            "validation", "Enter a valid email address", details={"fields": {"email": "invalid"}}
        )
    return email


@dataclass
class Auth:
    user: User
    session: Session


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


async def authenticate(db: AsyncSession, email: str, password: str) -> User:
    user = await db.scalar(select(User).where(User.email == email.strip().lower()))
    if user is None:
        verify_password(_DUMMY_HASH, password)
        raise ApiError("unauthorized", "Email or password is incorrect")
    if not verify_password(user.password_hash, password):
        raise ApiError("unauthorized", "Email or password is incorrect")
    return user


async def sign_up(
    db: AsyncSession, *, email: str, password: str, name: str, role: UserRole
) -> User:
    email = normalise_email(email)
    if len(password) < 8:
        raise ApiError(
            "validation",
            "Use at least 8 characters for the password",
            details={"fields": {"password": "too short"}},
        )
    user = User(email=email, name=name.strip(), role=role, password_hash=hash_password(password))
    db.add(user)
    try:
        await db.flush()
    except IntegrityError as e:
        await db.rollback()
        raise ApiError(
            "email_taken",
            "An account with this email already exists. Sign in instead.",
            status=409,
            details={"fields": {"email": "taken"}},
        ) from e
    return user


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


async def require_organiser(auth: Annotated[Auth, Depends(require_auth)]) -> Auth:
    if auth.user.role != UserRole.ORGANISER:
        raise ApiError("forbidden", "This page is for organisers")
    return auth


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
