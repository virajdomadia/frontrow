"""Auth routes (06 §C): email code → verify for the three doors, demo sign-in, sign-out, me,
and `POST/DELETE /auth/token` bearer sessions for the v4 app (same code flow)."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.db import get_session
from app.errors import ApiError
from app.models import User
from app.models.enums import SessionKind
from app.redis import optional_redis, require_redis
from app.schemas.auth import BusinessRef, CodeRequest, Demo, Me, Token, TokenRequest, Verify
from app.services import auth as svc
from app.services import demo as demo_svc
from app.services.auth import Auth, optional_auth, require_auth
from app.services.mail import mailer_for

router = APIRouter(prefix="/auth", tags=["auth"])

Db = Annotated[AsyncSession, Depends(get_session)]
Rds = Annotated[Redis, Depends(require_redis)]


def _settings(request: Request) -> Settings:
    return request.app.state.settings


async def me_of(db: AsyncSession, user: User) -> Me:
    return Me(
        id=user.id,
        name=user.name,
        email=user.email,
        is_staff=user.is_staff,
        is_demo=svc.is_demo(user),
        businesses=[
            BusinessRef(id=b.id, name=b.name, slug=b.slug, status=b.status.value, role=role)  # type: ignore[arg-type]
            for b, role in await svc.memberships(db, user)
        ],
    )


async def _start_web_session(
    request: Request, response: Response, db: AsyncSession, user: User
) -> Me:
    """Cookie session that adopts the visitor's `fr_sid`, so seats held before signing in
    stay theirs."""
    settings = _settings(request)
    sid = request.cookies.get(svc.SID_COOKIE)
    token, session = await svc.create_session(
        db, settings, user, kind=SessionKind.WEB, sid=sid, now=datetime.now(UTC)
    )
    svc.set_session_cookie(response, settings, token)
    if not sid and session.sid:
        svc.set_sid_cookie(response, settings, session.sid)
    response.headers["Cache-Control"] = "no-store"
    return await me_of(db, user)


@router.post("/code", status_code=204)
async def send_code(body: CodeRequest, request: Request, db: Db, redis: Rds) -> None:
    """Email a 6-digit code (10 minutes, 5 tries). Same answer at the staff door for any
    email. 429 when asked too often; 503 `email_unavailable` when this deployment has no SMTP."""
    await svc.request_code(
        db,
        redis,
        mailer_for(request.app),
        _settings(request),
        email=body.email,
        door=body.door,
        ip=svc.client_ip(request),
    )


@router.post(
    "/verify",
    response_model=Me,
    responses={
        401: {"description": "`code_invalid` — wrong or expired; `details.tries_left`"},
        422: {"description": "`name_required` / `business_required` — the code is still good"},
    },
)
async def verify(body: Verify, request: Request, response: Response, db: Db, redis: Rds) -> Me:
    user = await svc.verify(
        db,
        redis,
        _settings(request),
        email=body.email,
        code=body.code,
        door=body.door,
        name=body.name,
        business=svc.BusinessDetails(**body.business.model_dump()) if body.business else None,
    )
    return await _start_web_session(request, response, db, user)


@router.post("/demo", response_model=Me)
async def demo(
    body: Demo,
    request: Request,
    response: Response,
    db: Db,
    redis: Annotated[Redis | None, Depends(optional_redis)],
) -> Me:
    """One click, no email: the seeded demo customer, theatre owner (Orbit Cinemas) or staff
    member (view-only). The demo customer always has an upcoming and a past booking."""
    user = await db.scalar(select(User).where(User.email == svc.DEMO_EMAILS[body.as_]))
    if user is None:
        raise ApiError("not_found", "The demo accounts aren't seeded yet")
    if body.as_ == "customer":
        await demo_svc.ensure_bookings(db, redis, user, now=datetime.now(UTC))
    return await _start_web_session(request, response, db, user)


@router.post("/sign-out", status_code=204)
async def sign_out(request: Request, response: Response, db: Db) -> None:
    token = request.cookies.get(svc.SESSION_COOKIE)
    if token:
        await svc.revoke(db, _settings(request), token)
    svc.clear_session_cookie(response, _settings(request))


@router.get("/me", response_model=Me)
async def me(response: Response, db: Db, auth: Annotated[Auth, Depends(require_auth)]) -> Me:
    response.headers["Cache-Control"] = "no-store"
    return await me_of(db, auth.user)


@router.post("/token", response_model=Token, status_code=201)
async def create_token(body: TokenRequest, request: Request, db: Db, redis: Rds) -> Token:
    """Bearer session for the v4 app (`sessions.kind = mobile`, 90 days), from a code sent by
    `POST /auth/code` (existing accounts only)."""
    email = svc.normalise_email(body.email)
    user = await db.scalar(select(User).where(User.email == email))
    await svc.check_code(redis, _settings(request), email, body.code, consume=user is not None)
    if user is None:
        raise ApiError("code_invalid", "Sign up on the website first", status=401)
    token, session = await svc.create_session(
        db, _settings(request), user, kind=SessionKind.MOBILE, sid=None, now=datetime.now(UTC)
    )
    return Token(token=token, expires_at=session.expires_at, me=await me_of(db, user))


@router.delete("/token", status_code=204)
async def delete_token(
    request: Request, db: Db, auth: Annotated[Auth | None, Depends(optional_auth)]
) -> None:
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if auth is None or scheme.lower() != "bearer" or not token.strip():
        raise ApiError("unauthorized", "Send the bearer token to revoke")
    await svc.revoke(db, _settings(request), token.strip())
