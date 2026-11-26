"""The two screen templates: seat counts, no two seats overlap, every seat inside the
canvas, ids stitched into the layout JSON."""

import itertools
import math
import uuid

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas.layouts import GridKnobs, Knobs, Layout, StallsBalconyKnobs
from app.services.layouts import MARGIN, SEAT, generate, layout_json, seat_rows

KNOBS = TypeAdapter(Knobs)


@pytest.mark.parametrize(
    ("knobs", "expected"),
    [(GridKnobs(), 14 * 18), (StallsBalconyKnobs(), 12 * 28 + 6 * 24)],
)
def test_seat_count(knobs: Knobs, expected: int) -> None:
    gen = generate(knobs)
    assert gen.seat_count == expected
    assert gen.seat_count == len(list(seat_rows(gen)))


@pytest.mark.parametrize("knobs", [GridKnobs(), StallsBalconyKnobs()])
def test_no_overlap_and_inside_canvas(knobs: Knobs) -> None:
    gen = generate(knobs)
    points = [(x, y) for _, _, x, y in seat_rows(gen)]
    for x, y in points:
        assert MARGIN - 1 <= x - SEAT / 2 and x + SEAT / 2 <= gen.width - MARGIN + 1
        assert MARGIN - 1 <= y - SEAT / 2 and y + SEAT / 2 <= gen.height - MARGIN + 1
    # Pairwise on a sample keeps this fast.
    sample = points[:: max(1, len(points) // 400)]
    closest = min(math.dist(a, b) for a, b in itertools.combinations(sample, 2))
    assert closest >= SEAT  # never closer than a seat width


def test_seat_keys_are_unique() -> None:
    for knobs in (GridKnobs(), StallsBalconyKnobs()):
        keys = [key for key, *_ in seat_rows(generate(knobs))]
        assert len(keys) == len(set(keys))


def test_layout_json_matches_contract() -> None:
    gen = generate(StallsBalconyKnobs())
    ids = {key: str(uuid.uuid4()) for key, *_ in seat_rows(gen)}
    layout = Layout.model_validate(layout_json(gen, ids))
    assert layout.template == "stalls_balcony" and layout.stage.label == "SCREEN"
    assert [t.key for t in layout.tiers] == ["front", "rear", "balcony"]
    assert layout.sections[0].rows[0].seats[0].id == ids[("front", "A", 1)]
    # Row letters run on into the balcony, so "G9" names one seat in the whole screen.
    labels = [r.label for s in layout.sections for r in s.rows]
    assert len(labels) == len(set(labels))


def test_grid_tiers_are_row_bands() -> None:
    gen = generate(GridKnobs())
    assert [(s.key, len(s.rows)) for s in gen.sections] == [
        ("classic", 6),
        ("prime", 6),
        ("recliner", 2),
    ]
    assert gen.sections[0].rows[0].label == "A" and gen.sections[-1].rows[-1].label == "N"
    row = gen.sections[0].rows[0].seats
    # One centre aisle: the gap after seat 9 is wider than the pitch.
    assert row[9].x - row[8].x > row[8].x - row[7].x


def test_knobs_are_validated() -> None:
    assert isinstance(KNOBS.validate_python({"template": "grid"}), GridKnobs)
    with pytest.raises(ValidationError):
        KNOBS.validate_python({"template": "grid", "rows": 12})  # bands still sum to 14
    with pytest.raises(ValidationError):
        KNOBS.validate_python({"template": "arena"})  # dropped with the movies-only re-plan
    with pytest.raises(ValidationError):
        KNOBS.validate_python({"template": "dome"})
