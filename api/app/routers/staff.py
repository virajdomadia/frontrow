"""Frontrow staff routes (06 §C 🛠): staff only (customers and owners get 403); the demo staff
account reads everything and changes nothing (403 `demo_read_only`), and sees owners' contact
details masked and their request notes left out — anyone on the internet can open it."""

from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import EmailOutbox
from app.schemas.staff import (
    BusinessDecision,
    FilmIn,
    OutboxItem,
    RequestDecision,
    StaffBusiness,
    StaffCounts,
    StaffFilm,
    StaffFilmRequest,
)
from app.services import staff as svc
from app.services.auth import (
    Auth,
    initials,
    is_demo,
    mask_email,
    mask_phone,
    require_staff,
    require_staff_writer,
)

router = APIRouter(prefix="/staff", tags=["frontrow staff"])

Db = Annotated[AsyncSession, Depends(get_session)]
Reader = Annotated[Auth, Depends(require_staff)]
Writer = Annotated[Auth, Depends(require_staff_writer)]


def _now(response: Response) -> datetime:
    response.headers["Cache-Control"] = "no-store"
    return datetime.now(UTC)


@router.get("/counts", response_model=StaffCounts)
async def counts(response: Response, db: Db, staff: Reader) -> StaffCounts:
    _now(response)
    return await svc.counts(db)


@router.get("/films", response_model=list[StaffFilm])
async def films(response: Response, db: Db, staff: Reader) -> list[StaffFilm]:
    return await svc.list_films(db, _now(response))


@router.get("/films/{film_id}", response_model=StaffFilm)
async def film(film_id: str, response: Response, db: Db, staff: Reader) -> StaffFilm:
    return await svc.get_film(db, film_id, _now(response))


@router.post("/films", response_model=StaffFilm, status_code=201)
async def add_film(body: FilmIn, response: Response, db: Db, staff: Writer) -> StaffFilm:
    """Add a film to the shared catalogue; with `request_id`, the owner's request is answered."""
    return await svc.create_film(db, staff.user, body, _now(response))


@router.patch("/films/{film_id}", response_model=StaffFilm)
async def edit_film(
    film_id: str, body: FilmIn, response: Response, db: Db, staff: Writer
) -> StaffFilm:
    """Edit details or move the status on (coming soon → now showing → ended)."""
    return await svc.update_film(db, film_id, body, _now(response))


@router.get("/film-requests", response_model=list[StaffFilmRequest])
async def film_requests(
    response: Response,
    db: Db,
    staff: Reader,
    status: Literal["open", "added", "declined"] | None = None,
) -> list[StaffFilmRequest]:
    _now(response)
    out = await svc.list_requests(db, status)
    if is_demo(staff.user):
        for r in out:
            r.note = None
    return out


@router.patch("/film-requests/{request_id}", response_model=StaffFilmRequest)
async def decide_request(
    request_id: str, body: RequestDecision, response: Response, db: Db, staff: Writer
) -> StaffFilmRequest:
    """Decline with a reason, or link a film that is already in the catalogue."""
    _now(response)
    return await svc.decide_request(db, request_id, body)


@router.get("/businesses", response_model=list[StaffBusiness])
async def businesses(
    response: Response,
    db: Db,
    staff: Reader,
    status: Annotated[
        Literal["pending", "verified", "rejected", "suspended"] | None, Query()
    ] = None,
) -> list[StaffBusiness]:
    out = await svc.list_businesses(db, status, _now(response))
    if is_demo(staff.user):
        for b in out:
            b.phone = mask_phone(b.phone)
            for p in b.owners:
                p.name, p.email = initials(p.name), mask_email(p.email)
    return out


@router.patch("/businesses/{business_id}", response_model=StaffBusiness)
async def decide_business(
    business_id: str, body: BusinessDecision, response: Response, db: Db, staff: Writer
) -> StaffBusiness:
    """Approve (their shows go public) or reject with a reason."""
    return await svc.decide_business(db, business_id, body, _now(response))


@router.get("/outbox", response_model=list[OutboxItem])
async def email_outbox(response: Response, db: Db, staff: Reader) -> list[OutboxItem]:
    """The latest 100 customer emails with their send status: the preview of what customers
    get while SMTP is off. Demo staff see addresses masked."""
    _now(response)
    rows = await db.scalars(select(EmailOutbox).order_by(EmailOutbox.created_at.desc()).limit(100))
    demo = is_demo(staff.user)
    return [
        OutboxItem(
            id=r.id,
            to=mask_email(r.to_email) if demo else r.to_email,
            subject=r.subject,
            body=r.body,
            kind=r.kind,
            status=r.status,  # type: ignore[arg-type]
            error=r.error,
            order_id=r.order_id,
            created_at=r.created_at,
            sent_at=r.sent_at,
        )
        for r in rows
    ]
