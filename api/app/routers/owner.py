"""Theatre owner routes (06 §C 🎬): every route needs a business membership; another
business's ids are 404. All responses are per-user and `no-store`."""

from datetime import UTC, date, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.errors import ApiError
from app.schemas.layouts import Layout
from app.schemas.owner import (
    Bookings,
    BulkResult,
    BulkShows,
    BusinessPatch,
    CheckIn,
    CheckInResult,
    CinemaIn,
    FilmRequestIn,
    OwnerBusiness,
    OwnerCinema,
    OwnerFilmRequest,
    OwnerScreen,
    OwnerScreenDetail,
    OwnerShows,
    RegisterBusiness,
    ScreenIn,
    ScreenPreview,
)
from app.services import auth as auth_svc
from app.services import owner as svc
from app.services.auth import (
    Auth,
    Owner,
    refuse_demo,
    require_auth,
    require_owner,
    require_owner_writer,
)
from app.services.screens import preview

router = APIRouter(prefix="/owner", tags=["theatre owner"])
door = APIRouter(tags=["theatre owner"])

Db = Annotated[AsyncSession, Depends(get_session)]
Own = Annotated[Owner, Depends(require_owner)]
Writer = Annotated[Owner, Depends(require_owner_writer)]  # the demo owner only looks


def _now(response: Response) -> datetime:
    response.headers["Cache-Control"] = "no-store"
    return datetime.now(UTC)


@router.post("/business", response_model=OwnerBusiness, status_code=201)
async def register(
    body: RegisterBusiness,
    response: Response,
    db: Db,
    auth: Annotated[Auth, Depends(require_auth)],
) -> OwnerBusiness:
    """A signed-in account registers a business (pending until staff verify it)."""
    now = _now(response)
    refuse_demo(auth)
    if await auth_svc.memberships(db, auth.user):
        raise ApiError("conflict", "You already have a business on Frontrow")
    business = await auth_svc.register_business(
        db, auth.user, name=body.name, phone=body.phone, logo_url=None
    )
    await db.commit()
    return await svc.business_out(db, business, now)


@router.get("/business", response_model=OwnerBusiness)
async def business(response: Response, db: Db, owner: Own) -> OwnerBusiness:
    return await svc.business_out(db, owner.business, _now(response))


@router.patch("/business", response_model=OwnerBusiness)
async def patch_business(
    body: BusinessPatch, response: Response, db: Db, owner: Writer
) -> OwnerBusiness:
    return await svc.patch_business(db, owner.business, body, _now(response))


@router.get("/cinemas", response_model=list[OwnerCinema])
async def cinemas(response: Response, db: Db, owner: Own) -> list[OwnerCinema]:
    return await svc.list_cinemas(db, owner.business, _now(response))


@router.post("/cinemas", response_model=OwnerCinema, status_code=201)
async def add_cinema(body: CinemaIn, response: Response, db: Db, owner: Writer) -> OwnerCinema:
    return await svc.save_cinema(db, owner.business, body, _now(response))


@router.get("/cinemas/{cinema_id}", response_model=OwnerCinema)
async def cinema(cinema_id: str, response: Response, db: Db, owner: Own) -> OwnerCinema:
    now = _now(response)
    c = await svc.own_cinema(db, owner.business, cinema_id)
    return await svc.cinema_out(db, owner.business, c.id, now)


@router.patch("/cinemas/{cinema_id}", response_model=OwnerCinema)
async def edit_cinema(
    cinema_id: str, body: CinemaIn, response: Response, db: Db, owner: Writer
) -> OwnerCinema:
    return await svc.save_cinema(db, owner.business, body, _now(response), cinema_id=cinema_id)


@router.post("/cinemas/{cinema_id}/screens", response_model=OwnerScreen, status_code=201)
async def add_screen(
    cinema_id: str, body: ScreenIn, response: Response, db: Db, owner: Writer
) -> OwnerScreen:
    """Generate the seats from a template (grid, or stalls + balcony)."""
    return await svc.add_screen(db, owner.business, cinema_id, body, _now(response))


@router.post("/screens/preview", response_model=Layout)
async def preview_screen(body: ScreenPreview, owner: Own) -> Any:
    """The layout these knobs would produce — the live preview while setting up a screen."""
    return preview(body.knobs)


@router.get("/screens/{screen_id}", response_model=OwnerScreenDetail)
async def screen(screen_id: str, response: Response, db: Db, owner: Own) -> OwnerScreenDetail:
    return await svc.screen_detail(db, owner.business, screen_id, _now(response))


@router.get("/film-requests", response_model=list[OwnerFilmRequest])
async def film_requests(response: Response, db: Db, owner: Own) -> list[OwnerFilmRequest]:
    _now(response)
    return await svc.list_requests(db, owner.business)


@router.post("/film-requests", response_model=OwnerFilmRequest, status_code=201)
async def request_film(
    body: FilmRequestIn, response: Response, db: Db, owner: Writer
) -> OwnerFilmRequest:
    """Ask Frontrow staff to add a film that isn't in the catalogue yet."""
    _now(response)
    return await svc.request_film(db, owner.business, body)


@router.post(
    "/shows/bulk",
    response_model=BulkResult,
    status_code=201,
    responses={409: {"description": "`overlap` — `details.show` names the clashing show"}},
)
async def bulk_shows(body: BulkShows, response: Response, db: Db, owner: Writer) -> BulkResult:
    """Film + language + format + screen + days + times + a price per tier → every show in the
    range, or none if any of them overlaps another show on the screen."""
    return await svc.bulk_schedule(db, owner.business, body, _now(response))


@router.get("/shows", response_model=OwnerShows)
async def shows(
    response: Response,
    db: Db,
    owner: Own,
    date: Annotated[date | None, Query(description="IST day; default today")] = None,  # noqa: B008
) -> OwnerShows:
    return await svc.shows_on(db, owner.business, date, _now(response))


@router.get(
    "/shows/{show_id}/bookings",
    response_model=Bookings,
    responses={200: {"content": {"text/csv": {}}}},
)
async def bookings(
    show_id: str,
    request: Request,
    response: Response,
    db: Db,
    owner: Own,
    format: Annotated[str, Query(pattern="^(json|csv)$")] = "json",
) -> Any:
    data = await svc.bookings(db, owner.business, show_id, _now(response))
    if auth_svc.is_demo(owner.auth.user):  # the demo owner's customers are real people
        for b in data.bookings:
            b.name, b.email = auth_svc.initials(b.name), auth_svc.mask_email(b.email)
    if format == "csv":
        name = f"bookings-{data.show.film.slug}-{data.show.starts_at:%Y%m%d-%H%M}.csv"
        return PlainTextResponse(
            svc.bookings_csv(data),
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="{name}"',
                "Cache-Control": "no-store",
            },
        )
    return data


@door.post("/checkin", response_model=CheckInResult)
async def check_in(
    body: CheckIn, request: Request, response: Response, db: Db, owner: Writer
) -> CheckInResult:
    """The door (B10): valid once; then "already checked in at HH:MM"; wrong show; not a
    ticket. Only the business that owns the show can scan it."""
    return await svc.check_in(
        db,
        request.app.state.settings,
        owner.business,
        token=body.token,
        show_id=body.show_id,
        now=_now(response),
    )
