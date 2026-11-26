"""Auth routes (06 §C): sign-up / sign-in / sign-out / me / demo for the web's cookie session,
and `POST/DELETE /auth/token` bearer sessions so the v4 app needs no auth work."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.db import get_session
from app.errors import ApiError
from app.models import User
from app.models.enums import SessionKind, UserRole
from app.schemas.auth import Demo, Me, SignIn, SignUp, Token
from app.services import auth as svc
from app.services.auth import Auth, optional_auth, require_auth

router = APIRouter(prefix="/auth", tags=["auth"])

Db = Annotated[AsyncSession, Depends(get_session)]


def _settings(request: Request) -> Settings:
    return request.app.state.settings


def _me(user: User) -> Me:
    return Me(id=user.id, name=user.name, email=user.email, role=user.role.value)  # type: ignore[arg-type]


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
    return _me(user)


@router.post("/sign-up", response_model=Me, status_code=201)
async def sign_up(body: SignUp, request: Request, response: Response, db: Db) -> Me:
    user = await svc.sign_up(
        db, email=body.email, password=body.password, name=body.name, role=UserRole(body.role)
    )
    return await _start_web_session(request, response, db, user)


@router.post("/sign-in", response_model=Me)
async def sign_in(body: SignIn, request: Request, response: Response, db: Db) -> Me:
    user = await svc.authenticate(db, body.email, body.password)
    return await _start_web_session(request, response, db, user)


@router.post("/demo", response_model=Me)
async def demo(body: Demo, request: Request, response: Response, db: Db) -> Me:
    user = await db.scalar(select(User).where(User.email == svc.DEMO_EMAILS[body.as_]))
    if user is None:
        raise ApiError("not_found", "The demo accounts aren't seeded yet")
    return await _start_web_session(request, response, db, user)


@router.post("/sign-out", status_code=204)
async def sign_out(request: Request, response: Response, db: Db) -> None:
    token = request.cookies.get(svc.SESSION_COOKIE)
    if token:
        await svc.revoke(db, _settings(request), token)
    svc.clear_session_cookie(response, _settings(request))


@router.get("/me", response_model=Me)
async def me(response: Response, auth: Annotated[Auth, Depends(require_auth)]) -> Me:
    response.headers["Cache-Control"] = "no-store"
    return _me(auth.user)


@router.post("/token", response_model=Token, status_code=201)
async def create_token(body: SignIn, request: Request, db: Db) -> Token:
    """Bearer session for the v4 app (`sessions.kind = mobile`, 90 days)."""
    user = await svc.authenticate(db, body.email, body.password)
    token, session = await svc.create_session(
        db, _settings(request), user, kind=SessionKind.MOBILE, sid=None, now=datetime.now(UTC)
    )
    return Token(token=token, expires_at=session.expires_at, me=_me(user))


@router.delete("/token", status_code=204)
async def delete_token(
    request: Request, db: Db, auth: Annotated[Auth | None, Depends(optional_auth)]
) -> None:
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if auth is None or scheme.lower() != "bearer" or not token.strip():
        raise ApiError("unauthorized", "Send the bearer token to revoke")
    await svc.revoke(db, _settings(request), token.strip())
