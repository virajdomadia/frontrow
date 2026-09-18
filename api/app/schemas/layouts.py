"""Template knobs (04 §2) — validated here so the organiser POST in F7 and the seed share one
definition — and the `Layout` JSON shape the seat map renders (06 §D)."""

from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas import ApiModel


class TierBand(BaseModel):
    """A run of rows sharing one tier, front to back (grid) — bands sum to `rows`."""

    key: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,23}$")
    label: str = Field(min_length=1, max_length=40)
    rows: Annotated[int, Field(ge=1, le=20)]


class GridKnobs(BaseModel):
    """Straight rows, one centre aisle, tiers by row band (a cinema screen)."""

    template: Literal["grid"] = "grid"
    rows: Annotated[int, Field(ge=8, le=20)] = 14
    seats_per_row: Annotated[int, Field(ge=10, le=24)] = 18
    aisle_after: Annotated[int, Field(ge=2, le=22)] = 9
    stage_label: str = "SCREEN"
    tiers: list[TierBand] = Field(
        default_factory=lambda: [
            TierBand(key="classic", label="Classic", rows=6),
            TierBand(key="prime", label="Prime", rows=6),
            TierBand(key="recliner", label="Recliner", rows=2),
        ],
        min_length=1,
        max_length=4,
    )

    @model_validator(mode="after")
    def _bands_match_rows(self) -> "GridKnobs":
        total = sum(t.rows for t in self.tiers)
        if total != self.rows:
            raise ValueError(f"tier bands cover {total} rows, venue has {self.rows}")
        if self.aisle_after >= self.seats_per_row:
            raise ValueError("aisle_after must be inside the row")
        if len({t.key for t in self.tiers}) != len(self.tiers):
            raise ValueError("tier keys must be unique")
        return self


class StallsBalconyKnobs(BaseModel):
    """Two curved blocks — stalls split into front/rear tiers, a balcony behind an aisle."""

    template: Literal["stalls_balcony"] = "stalls_balcony"
    stalls_rows: Annotated[int, Field(ge=8, le=16)] = 12
    stalls_seats: Annotated[int, Field(ge=18, le=36)] = 28
    front_rows: Annotated[int, Field(ge=2, le=8)] = 5
    balcony_rows: Annotated[int, Field(ge=3, le=10)] = 6
    balcony_seats: Annotated[int, Field(ge=14, le=30)] = 24
    curve: Annotated[float, Field(ge=0.0, le=1.0)] = 0.5
    stage_label: str = "STAGE"

    @model_validator(mode="after")
    def _front_inside_stalls(self) -> "StallsBalconyKnobs":
        if self.front_rows >= self.stalls_rows:
            raise ValueError("front_rows must leave at least one rear row")
        return self


class ArenaKnobs(BaseModel):
    """Wedge sections around a floor block, stage at the top; tier by distance from the stage."""

    template: Literal["arena"] = "arena"
    sections: Annotated[int, Field(ge=6, le=12)] = 8
    rows_per_section: Annotated[int, Field(ge=6, le=14)] = 12
    seats_per_row: Annotated[int, Field(ge=10, le=20)] = 16
    floor_rows: Annotated[int, Field(ge=0, le=24)] = 20
    floor_seats: Annotated[int, Field(ge=0, le=24)] = 20
    floor_radius: Annotated[int, Field(ge=200, le=420)] = 360
    stage_label: str = "STAGE"


Knobs = Annotated[GridKnobs | StallsBalconyKnobs | ArenaKnobs, Field(discriminator="template")]


# --- The Layout JSON (06 §D) ----------------------------------------------------------------------


class LayoutSeat(ApiModel):
    id: str
    n: int
    x: int
    y: int


class LayoutRow(ApiModel):
    label: str
    seats: list[LayoutSeat]


class LayoutSection(ApiModel):
    key: str
    label: str
    tier: str
    shape: Literal["rows", "wedge"]
    polygon: list[list[int]] | None = None
    rows: list[LayoutRow]


class LayoutStage(ApiModel):
    label: str
    x: int
    y: int
    w: int


class Layout(ApiModel):
    template: Literal["grid", "stalls_balcony", "arena"]
    width: int
    height: int
    stage: LayoutStage
    tiers: list[dict[str, str]] = Field(
        description="`{key, label}` in price order, front to back — the legend."
    )
    sections: list[LayoutSection]
