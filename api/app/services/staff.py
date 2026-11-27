"""Frontrow staff (R11): the shared film catalogue, owners' film requests, and approving new
businesses. Approval is what makes a business's shows public."""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import ApiError
from app.models import Business, BusinessMember, Cinema, Film, FilmRequest, Screen, Show, User
from app.models.enums import BusinessStatus, Cert, FilmStatus, RequestStatus, ShowStatus
from app.schemas.catalog import CastMember
from app.schemas.owner import FilmRef
from app.schemas.staff import (
    BusinessDecision,
    FilmIn,
    Person,
    RequestDecision,
    StaffBusiness,
    StaffBusinessRef,
    StaffCinema,
    StaffCounts,
    StaffFilm,
    StaffFilmRequest,
)
from app.services.auth import slugify
from app.services.catalog import card
from app.services.shows import parse_id


async def counts(db: AsyncSession) -> StaffCounts:
    return StaffCounts(
        pending_businesses=await db.scalar(
            select(func.count())
            .select_from(Business)
            .where(Business.status == BusinessStatus.PENDING)
        )
        or 0,
        open_requests=await db.scalar(
            select(func.count())
            .select_from(FilmRequest)
            .where(FilmRequest.status == RequestStatus.OPEN)
        )
        or 0,
        films=await db.scalar(select(func.count()).select_from(Film)) or 0,
    )


# --- films ----------------------------------------------------------------------------------------


async def _upcoming_by_film(db: AsyncSession, now: datetime) -> dict[uuid.UUID, int]:
    rows = await db.execute(
        select(Show.film_id, func.count())
        .where(Show.starts_at > now, Show.status == ShowStatus.SCHEDULED)
        .group_by(Show.film_id)
    )
    return {k: v for k, v in rows.tuples()}


def film_out(film: Film, scheduled: int) -> StaffFilm:
    return StaffFilm(
        **card(film, []).model_dump(exclude={"show_count", "from_price_paise"}),
        show_count=0,
        from_price_paise=None,
        synopsis=film.synopsis,
        cast_crew=[CastMember(**c) for c in film.cast_crew],
        trailer_url=film.trailer_url,
        created_at=film.created_at,
        scheduled_shows=scheduled,
    )


async def list_films(db: AsyncSession, now: datetime) -> list[StaffFilm]:
    upcoming = await _upcoming_by_film(db, now)
    order = {FilmStatus.NOW_SHOWING: 0, FilmStatus.COMING_SOON: 1, FilmStatus.ENDED: 2}
    films = sorted(await db.scalars(select(Film)), key=lambda f: (order[f.status], f.title))
    return [film_out(f, upcoming.get(f.id, 0)) for f in films]


async def get_film(db: AsyncSession, film_id: str, now: datetime) -> StaffFilm:
    film = await db.get(Film, parse_id(film_id, "film"))
    if film is None:
        raise ApiError("not_found", "No such film")
    return film_out(film, (await _upcoming_by_film(db, now)).get(film.id, 0))


async def _slug(db: AsyncSession, title: str, keep: uuid.UUID | None) -> str:
    base = slugify(title, "film")
    q = select(Film.slug).where(Film.slug.like(f"{base}%"))
    if keep is not None:
        q = q.where(Film.id != keep)
    taken = set(await db.scalars(q))
    if base not in taken:
        return base
    n = 2
    while f"{base}-{n}" in taken:
        n += 1
    return f"{base}-{n}"


def _apply(film: Film, body: FilmIn) -> None:
    film.title = body.title.strip()
    film.synopsis = body.synopsis.strip()
    film.cast_crew = [c.model_dump() for c in body.cast_crew]
    film.runtime_min = body.runtime_min
    film.cert = Cert(body.cert) if body.cert else None
    film.genres = list(body.genres)
    film.languages = list(body.languages)
    film.formats = list(body.formats)
    film.poster_url = body.poster_url
    film.banner_url = body.banner_url
    film.trailer_url = body.trailer_url
    film.release_date = body.release_date
    film.status = FilmStatus(body.status)


async def create_film(db: AsyncSession, user: User, body: FilmIn, now: datetime) -> StaffFilm:
    req = None
    if body.request_id is not None:
        req = await db.get(FilmRequest, body.request_id)
        if req is None:
            raise ApiError("not_found", "No such film request")
        if req.status != RequestStatus.OPEN:
            raise ApiError("conflict", "That request was already answered")
    film = Film(slug=await _slug(db, body.title, None), created_by=user.id)
    _apply(film, body)
    db.add(film)
    await db.flush()
    if req is not None:
        req.status = RequestStatus.ADDED
        req.film_id = film.id
    await db.commit()
    return film_out(film, 0)


async def update_film(db: AsyncSession, film_id: str, body: FilmIn, now: datetime) -> StaffFilm:
    film = await db.get(Film, parse_id(film_id, "film"))
    if film is None:
        raise ApiError("not_found", "No such film")
    if body.title.strip() != film.title:
        film.slug = await _slug(db, body.title, film.id)
    _apply(film, body)
    await db.commit()
    return await get_film(db, str(film.id), now)


# --- requests -------------------------------------------------------------------------------------


async def list_requests(db: AsyncSession, status: str | None) -> list[StaffFilmRequest]:
    q = (
        select(FilmRequest, Business, Film)
        .join(Business, Business.id == FilmRequest.business_id)
        .outerjoin(Film, Film.id == FilmRequest.film_id)
        .order_by(FilmRequest.created_at.desc())
    )
    if status:
        q = q.where(FilmRequest.status == RequestStatus(status))
    return [
        StaffFilmRequest(
            id=r.id,
            title=r.title,
            note=r.note,
            status=r.status.value,  # type: ignore[arg-type]
            reply=r.reply,
            business=StaffBusinessRef(id=b.id, name=b.name),
            film=FilmRef(id=f.id, slug=f.slug, title=f.title) if f else None,
            created_at=r.created_at,
        )
        for r, b, f in (await db.execute(q)).tuples()
    ]


async def decide_request(
    db: AsyncSession, request_id: str, body: RequestDecision
) -> StaffFilmRequest:
    req = await db.get(FilmRequest, parse_id(request_id, "film request"))
    if req is None:
        raise ApiError("not_found", "No such film request")
    if req.status != RequestStatus.OPEN:
        raise ApiError("conflict", "That request was already answered")
    if body.action == "decline":
        reply = (body.reply or "").strip()
        if not reply:
            raise ApiError(
                "validation", "Say why", details={"fields": {"reply": "Give the owner a reason"}}
            )
        req.status, req.reply = RequestStatus.DECLINED, reply
    else:
        film = await db.get(Film, body.film_id) if body.film_id else None
        if film is None:
            raise ApiError(
                "validation", "Pick the film", details={"fields": {"film_id": "required"}}
            )
        req.status, req.film_id = RequestStatus.ADDED, film.id
    await db.commit()
    return next(r for r in await list_requests(db, None) if r.id == req.id)


# --- businesses -----------------------------------------------------------------------------------


async def list_businesses(
    db: AsyncSession, status: str | None, now: datetime
) -> list[StaffBusiness]:
    q = select(Business).order_by(Business.created_at.desc())
    if status:
        q = q.where(Business.status == BusinessStatus(status))
    businesses = list(await db.scalars(q))
    if not businesses:
        return []
    ids = [b.id for b in businesses]
    owners: dict[uuid.UUID, list[Person]] = defaultdict(list)
    for bid, name, email in (
        await db.execute(
            select(BusinessMember.business_id, User.name, User.email)
            .join(User, User.id == BusinessMember.user_id)
            .where(BusinessMember.business_id.in_(ids))
        )
    ).tuples():
        owners[bid].append(Person(name=name, email=email))
    cinemas: dict[uuid.UUID, list[StaffCinema]] = defaultdict(list)
    screen_stats = {
        cid: (n, seats)
        for cid, n, seats in (
            await db.execute(
                select(
                    Screen.cinema_id, func.count(), func.coalesce(func.sum(Screen.seat_count), 0)
                ).group_by(Screen.cinema_id)
            )
        ).tuples()
    }
    for c in await db.scalars(
        select(Cinema).where(Cinema.business_id.in_(ids)).order_by(Cinema.created_at)
    ):
        n, seats = screen_stats.get(c.id, (0, 0))
        cinemas[c.business_id].append(
            StaffCinema(
                id=c.id, name=c.name, area=c.area, address=c.address, screens=n, seats=int(seats)
            )
        )
    shows = {
        bid: n
        for bid, n in (
            await db.execute(
                select(Cinema.business_id, func.count())
                .join(Screen, Screen.cinema_id == Cinema.id)
                .join(Show, Show.screen_id == Screen.id)
                .where(
                    Cinema.business_id.in_(ids),
                    Show.starts_at > now,
                    Show.status == ShowStatus.SCHEDULED,
                )
                .group_by(Cinema.business_id)
            )
        ).tuples()
    }
    return [
        StaffBusiness(
            id=b.id,
            name=b.name,
            slug=b.slug,
            phone=b.phone,
            status=b.status.value,  # type: ignore[arg-type]
            review_note=b.review_note,
            created_at=b.created_at,
            verified_at=b.verified_at,
            owners=owners[b.id],
            cinemas=cinemas[b.id],
            scheduled_shows=shows.get(b.id, 0),
        )
        for b in businesses
    ]


async def decide_business(
    db: AsyncSession, business_id: str, body: BusinessDecision, now: datetime
) -> StaffBusiness:
    business = await db.get(Business, parse_id(business_id, "business"))
    if business is None:
        raise ApiError("not_found", "No such business")
    if body.action == "approve":
        business.status = BusinessStatus.VERIFIED
        business.verified_at = now
        business.review_note = None
    else:
        note = (body.note or "").strip()
        if not note:
            raise ApiError(
                "validation", "Say why", details={"fields": {"note": "Give the owner a reason"}}
            )
        business.status = BusinessStatus.REJECTED
        business.review_note = note
        business.verified_at = None
    await db.commit()
    return next(b for b in await list_businesses(db, None, now) if b.id == business.id)
