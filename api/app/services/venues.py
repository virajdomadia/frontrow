"""Venue generation, shared by the seed and the organiser console (F7): knobs → layout JSON +
one `seats` row per seat, with the stored ids stitched back into the layout."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Seat, Venue
from app.models.enums import LayoutTemplate
from app.services.layouts import generate, layout_json, seat_rows


def preview(knobs: Any) -> dict[str, Any]:
    """The layout a set of knobs would produce, with throwaway ids — the console's live preview."""
    gen = generate(knobs)
    ids = {key: f"preview-{i}" for i, (key, *_rest) in enumerate(seat_rows(gen))}
    return layout_json(gen, ids)


async def create_venue(
    db: AsyncSession,
    organiser_id: uuid.UUID,
    *,
    name: str,
    address: str,
    photo_url: str | None,
    knobs: Any,
) -> Venue:
    """Generate the layout, insert the seat rows, store the layout JSON with their ids."""
    gen = generate(knobs)
    venue = Venue(
        organiser_id=organiser_id,
        name=name,
        address=address,
        photo_url=photo_url,
        template=LayoutTemplate(knobs.template),
        knobs=knobs.model_dump(),
        layout={},
        seat_count=gen.seat_count,
    )
    db.add(venue)
    await db.flush()
    rows = []
    ids: dict[tuple[str, str, int], str] = {}
    for key, tier, x, y in seat_rows(gen):
        seat_id = uuid.uuid4()
        ids[key] = str(seat_id)
        rows.append(
            {
                "id": seat_id,
                "venue_id": venue.id,
                "section_key": key[0],
                "row_label": key[1],
                "number": key[2],
                "tier_key": tier,
                "x": x,
                "y": y,
            }
        )
    await db.execute(insert(Seat), rows)
    venue.layout = layout_json(gen, ids)
    await db.flush()
    return venue
