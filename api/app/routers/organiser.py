"""Organiser console routes (06 §C 🏟): every route needs an organiser session and only ever
sees that organiser's own venues, events and showtimes."""

from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Response
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.schemas.layouts import Layout
from app.schemas.organiser import (
    Bookings,
    CreateShowtime,
    CreateVenue,
    EventFields,
    EventPatch,
    OrganiserEvent,
    OrganiserShowtime,
    OrganiserVenue,
    OrganiserVenueDetail,
    ShowtimePatch,
    VenuePreview,
)
from app.services import organiser as svc
from app.services.auth import Auth, require_organiser
from app.services.venues import preview

router = APIRouter(prefix="/organiser", tags=["organiser"])

Db = Annotated[AsyncSession, Depends(get_session)]
Organiser = Annotated[Auth, Depends(require_organiser)]


def _no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


# --- venues ---------------------------------------------------------------------------------------


@router.get("/venues", response_model=list[OrganiserVenue])
async def list_venues(response: Response, db: Db, auth: Organiser) -> list[OrganiserVenue]:
    _no_store(response)
    return await svc.list_venues(db, auth.user, datetime.now(UTC))


@router.post("/venues/preview", response_model=Layout)
async def preview_venue(body: VenuePreview, auth: Organiser) -> Any:
    """The layout these knobs would generate — nothing is saved (the live preview)."""
    return preview(body.knobs)


@router.post("/venues", response_model=OrganiserVenue, status_code=201)
async def create_venue(body: CreateVenue, db: Db, auth: Organiser) -> OrganiserVenue:
    return await svc.add_venue(db, auth.user, body, datetime.now(UTC))


@router.get("/venues/{venue_id}", response_model=OrganiserVenueDetail)
async def get_venue(
    venue_id: str, response: Response, db: Db, auth: Organiser
) -> OrganiserVenueDetail:
    _no_store(response)
    return await svc.venue_detail(db, auth.user, venue_id, datetime.now(UTC))


# --- events ---------------------------------------------------------------------------------------


@router.get("/events", response_model=list[OrganiserEvent])
async def list_events(response: Response, db: Db, auth: Organiser) -> list[OrganiserEvent]:
    _no_store(response)
    return await svc.list_events(db, auth.user, datetime.now(UTC))


@router.post("/events", response_model=OrganiserEvent, status_code=201)
async def create_event(body: EventFields, db: Db, auth: Organiser) -> OrganiserEvent:
    return await svc.add_event(db, auth.user, body, datetime.now(UTC))


@router.get("/events/{event_id}", response_model=OrganiserEvent)
async def get_event(event_id: str, response: Response, db: Db, auth: Organiser) -> OrganiserEvent:
    _no_store(response)
    return await svc.event_detail(db, auth.user, event_id, datetime.now(UTC))


@router.patch("/events/{event_id}", response_model=OrganiserEvent)
async def edit_event(event_id: str, body: EventPatch, db: Db, auth: Organiser) -> OrganiserEvent:
    return await svc.edit_event(db, auth.user, event_id, body, datetime.now(UTC))


# --- showtimes ------------------------------------------------------------------------------------


@router.get("/showtimes", response_model=list[OrganiserShowtime])
async def list_showtimes(
    response: Response, db: Db, auth: Organiser, event_id: str | None = None
) -> list[OrganiserShowtime]:
    _no_store(response)
    return await svc.list_showtimes(db, auth.user, event_id=event_id)


@router.post("/showtimes", response_model=OrganiserShowtime, status_code=201)
async def create_showtime(body: CreateShowtime, db: Db, auth: Organiser) -> OrganiserShowtime:
    return await svc.add_showtime(db, auth.user, body, datetime.now(UTC))


@router.get("/showtimes/{showtime_id}", response_model=OrganiserShowtime)
async def get_showtime(
    showtime_id: str, response: Response, db: Db, auth: Organiser
) -> OrganiserShowtime:
    _no_store(response)
    return await svc.showtime_detail(db, auth.user, showtime_id)


@router.patch(
    "/showtimes/{showtime_id}",
    response_model=OrganiserShowtime,
    responses={409: {"description": "`has_sales` — tickets are sold, so no cancel or move"}},
)
async def edit_showtime(
    showtime_id: str, body: ShowtimePatch, db: Db, auth: Organiser
) -> OrganiserShowtime:
    return await svc.edit_showtime(db, auth.user, showtime_id, body, datetime.now(UTC))


@router.get(
    "/showtimes/{showtime_id}/bookings",
    response_model=Bookings,
    responses={200: {"content": {"text/csv": {}}, "description": "JSON, or CSV with ?format=csv"}},
)
async def get_bookings(
    showtime_id: str,
    response: Response,
    db: Db,
    auth: Organiser,
    format: Literal["json", "csv"] = "json",
) -> Any:
    data = await svc.bookings(db, auth.user, showtime_id)
    if format == "csv":
        name = f"{data.showtime.event.slug}-{data.showtime.starts_at:%Y%m%d-%H%M}-bookings.csv"
        return PlainTextResponse(
            svc.bookings_csv(data),
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="{name}"',
                "Cache-Control": "no-store",
            },
        )
    _no_store(response)
    return data
