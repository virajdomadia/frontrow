"""The two screen templates (04 §2): knobs → seat positions + the `Layout` JSON. (The arena
was dropped with the movies-only re-plan.)

Geometry is in layout units (= CSS px at 1×): a seat is 26 wide on a 34 pitch, an aisle adds
44, and every template is normalised so its bounding box starts at MARGIN. Seats are generated
without ids — `seat_rows()` gives the rows to insert, `layout_json()` stitches the stored ids
back in — so the JSON the map renders keys on the same UUIDs holds and tickets use.
"""

import math
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from app.schemas.layouts import GridKnobs, Knobs, StallsBalconyKnobs

SEAT = 26
PITCH = 34
AISLE = 44
MARGIN = 40
STAGE_H = 24
ROW_LABELS = [chr(ord("A") + i) for i in range(26)]


@dataclass
class GenSeat:
    n: int
    x: float
    y: float


@dataclass
class GenRow:
    label: str
    seats: list[GenSeat]


@dataclass
class GenSection:
    key: str
    label: str
    tier: str
    shape: str  # rows | wedge
    rows: list[GenRow]
    polygon: list[tuple[float, float]] | None = None


@dataclass
class Generated:
    template: str
    stage: dict[str, Any]
    tiers: list[dict[str, str]]
    sections: list[GenSection]
    width: int = 0
    height: int = 0

    @property
    def seat_count(self) -> int:
        return sum(len(r.seats) for s in self.sections for r in s.rows)


SeatKey = tuple[str, str, int]  # (section_key, row_label, number)


def generate(knobs: Knobs) -> Generated:
    if isinstance(knobs, GridKnobs):
        gen = _grid(knobs)
    elif isinstance(knobs, StallsBalconyKnobs):
        gen = _stalls_balcony(knobs)
    else:  # pragma: no cover — the discriminated union already rejects this
        raise ValueError(f"unknown template {knobs!r}")
    _normalise(gen)
    return gen


def seat_rows(gen: Generated) -> Iterator[tuple[SeatKey, str, int, int]]:
    """Every seat as `((section_key, row_label, number), tier_key, x, y)` — the `seats` rows."""
    for section in gen.sections:
        for row in section.rows:
            for seat in row.seats:
                yield (section.key, row.label, seat.n), section.tier, round(seat.x), round(seat.y)


def layout_json(gen: Generated, ids: dict[SeatKey, str]) -> dict[str, Any]:
    """The `Layout` document (06 §D) with the stored seat ids stitched in."""
    return {
        "template": gen.template,
        "width": gen.width,
        "height": gen.height,
        "stage": gen.stage,
        "tiers": gen.tiers,
        "sections": [
            {
                "key": s.key,
                "label": s.label,
                "tier": s.tier,
                "shape": s.shape,
                **({"polygon": [[round(x), round(y)] for x, y in s.polygon]} if s.polygon else {}),
                "rows": [
                    {
                        "label": r.label,
                        "seats": [
                            {
                                "id": ids[(s.key, r.label, seat.n)],
                                "n": seat.n,
                                "x": round(seat.x),
                                "y": round(seat.y),
                            }
                            for seat in r.seats
                        ],
                    }
                    for r in s.rows
                ],
            }
            for s in gen.sections
        ],
    }


# --- grid -----------------------------------------------------------------------------------------


def _grid(k: GridKnobs) -> Generated:
    """Straight rows under the screen; one centre aisle; tiers are row bands front to back."""
    sections: list[GenSection] = []
    row_index = 0
    for band in k.tiers:
        rows: list[GenRow] = []
        for _ in range(band.rows):
            y = row_index * PITCH
            seats = []
            for n in range(1, k.seats_per_row + 1):
                x = (n - 1) * PITCH + (AISLE if n > k.aisle_after else 0)
                seats.append(GenSeat(n=n, x=x, y=y))
            rows.append(GenRow(label=ROW_LABELS[row_index], seats=seats))
            row_index += 1
        sections.append(
            GenSection(key=band.key, label=band.label, tier=band.key, shape="rows", rows=rows)
        )
    width = (k.seats_per_row - 1) * PITCH + AISLE
    stage = {"label": k.stage_label, "x": 0, "y": -(PITCH * 2 + STAGE_H), "w": width}
    tiers = [{"key": b.key, "label": b.label} for b in k.tiers]
    return Generated(template="grid", stage=stage, tiers=tiers, sections=sections)


# --- stalls + balcony -----------------------------------------------------------------------------


def _arc_row(n_seats: int, radius: float, cy: float) -> list[GenSeat]:
    """`n_seats` on an arc of `radius` centred at (0, cy), chord spacing = PITCH, facing up."""
    step = PITCH / radius
    start = math.pi / 2 - step * (n_seats - 1) / 2
    seats = []
    for n in range(1, n_seats + 1):
        theta = start + step * (n - 1)
        seats.append(GenSeat(n=n, x=radius * math.cos(theta), y=cy + radius * math.sin(theta)))
    return seats


def _stalls_balcony(k: StallsBalconyKnobs) -> Generated:
    """Rows on arcs around the stage; the balcony block sits behind a wide aisle."""
    # curve 0 → almost flat rows (huge radius); curve 1 → tight arcs.
    base_radius = 700 + (1 - k.curve) * 2400
    cy = -base_radius  # arc centre above the stage so row A is the innermost arc
    sections: list[GenSection] = []

    def block(
        key: str, label: str, tier: str, first_row: int, n_rows: int, seats: int, offset: float
    ) -> None:
        rows = []
        for i in range(n_rows):
            r = first_row + i
            radius = base_radius + offset + r * PITCH
            rows.append(GenRow(label=ROW_LABELS[r], seats=_arc_row(seats, radius, cy)))
        sections.append(GenSection(key=key, label=label, tier=tier, shape="rows", rows=rows))

    rear_rows = k.stalls_rows - k.front_rows
    block("front", "Front stalls", "front", 0, k.front_rows, k.stalls_seats, 0)
    block("rear", "Rear stalls", "rear", k.front_rows, rear_rows, k.stalls_seats, 0)
    block("balcony", "Balcony", "balcony", k.stalls_rows, k.balcony_rows, k.balcony_seats, AISLE)

    w = (k.stalls_seats - 1) * PITCH * 0.7
    stage = {"label": k.stage_label, "x": -w / 2, "y": -(PITCH * 2 + STAGE_H), "w": w}
    tiers = [
        {"key": "front", "label": "Front stalls"},
        {"key": "rear", "label": "Rear stalls"},
        {"key": "balcony", "label": "Balcony"},
    ]
    return Generated(template="stalls_balcony", stage=stage, tiers=tiers, sections=sections)


# --- normalise ------------------------------------------------------------------------------------


def _normalise(gen: Generated) -> None:
    """Shift everything so the bounding box (seats, polygons, stage) starts at MARGIN and set
    width/height; then round to ints."""
    xs: list[float] = [gen.stage["x"], gen.stage["x"] + gen.stage["w"]]
    ys: list[float] = [gen.stage["y"], gen.stage["y"] + STAGE_H]
    for s in gen.sections:
        for r in s.rows:
            for seat in r.seats:
                xs += [seat.x - SEAT / 2, seat.x + SEAT / 2]
                ys += [seat.y - SEAT / 2, seat.y + SEAT / 2]
        for x, y in s.polygon or []:
            xs.append(x)
            ys.append(y)
    dx = MARGIN - min(xs)
    dy = MARGIN - min(ys)
    for s in gen.sections:
        for r in s.rows:
            for seat in r.seats:
                seat.x += dx
                seat.y += dy
        if s.polygon:
            s.polygon = [(x + dx, y + dy) for x, y in s.polygon]
    gen.stage = {
        "label": gen.stage["label"],
        "x": round(gen.stage["x"] + dx),
        "y": round(gen.stage["y"] + dy),
        "w": round(gen.stage["w"]),
    }
    gen.width = round(max(xs) + dx + MARGIN)
    gen.height = round(max(ys) + dy + MARGIN)
