"""Screen generation, shared by the seed and the owner console (B8): knobs → layout JSON + one
`seats` row per seat, with the stored ids stitched back into the layout."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Screen, Seat
from app.models.enums import LayoutTemplate
from app.services.layouts import generate, layout_json, seat_rows


def preview(knobs: Any) -> dict[str, Any]:
    """The layout a set of knobs would produce, with throwaway ids — the console's live preview."""
    gen = generate(knobs)
    ids = {key: f"preview-{i}" for i, (key, *_rest) in enumerate(seat_rows(gen))}
    return layout_json(gen, ids)


async def create_screen(
    db: AsyncSession,
    cinema_id: uuid.UUID,
    *,
    name: str,
    formats: list[str],
    knobs: Any,
) -> Screen:
    """Generate the layout, insert the seat rows, store the layout JSON with their ids."""
    gen = generate(knobs)
    screen = Screen(
        cinema_id=cinema_id,
        name=name,
        template=LayoutTemplate(knobs.template),
        knobs=knobs.model_dump(),
        layout={},
        tiers=gen.tiers,
        formats=formats,
        seat_count=gen.seat_count,
    )
    db.add(screen)
    await db.flush()
    rows = []
    ids: dict[tuple[str, str, int], str] = {}
    for key, tier, x, y in seat_rows(gen):
        seat_id = uuid.uuid4()
        ids[key] = str(seat_id)
        rows.append(
            {
                "id": seat_id,
                "screen_id": screen.id,
                "section_key": key[0],
                "row_label": key[1],
                "number": key[2],
                "tier_key": tier,
                "x": x,
                "y": y,
            }
        )
    await db.execute(insert(Seat), rows)
    screen.layout = layout_json(gen, ids)
    await db.flush()
    return screen
