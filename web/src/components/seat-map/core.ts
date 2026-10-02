/**
 * Seat-map core — pure TypeScript: no DOM, no React, no imports. v4's React Native map reuses
 * this file unchanged (docs/07-plan.md F1), so everything here works on plain data:
 *
 * - `indexLayout`  Layout JSON → placed seats, rows, sections, a spatial hash
 * - `hitTest`      layout point → seat id (taps); `sectionAt` → section key (arena overview)
 * - `neighbour`    arrow-key movement between seats
 * - `SeatState`    the live state (sold / held / mine) with snapshot + diff merge (06 §D)
 * - `tierPalette`  tier key → colour token, by price
 *
 * Coordinates are layout units (= CSS px at 1×); a seat's `x, y` is its centre.
 */

export const SEAT = 26;
export const PITCH = 34;

// --- Layout (06 §D) — structural, so the web's generated types and the app's both fit -------------

export type LayoutSeat = { id: string; n: number; x: number; y: number };
export type LayoutRow = { label: string; seats: LayoutSeat[] };
export type LayoutSection = {
  key: string;
  label: string;
  tier: string;
  shape: "rows" | "wedge";
  polygon?: number[][] | null;
  rows: LayoutRow[];
};
export type Layout = {
  template: "grid" | "stalls_balcony" | "arena";
  width: number;
  height: number;
  stage: { label: string; x: number; y: number; w: number };
  tiers: { key: string; label: string }[];
  sections: LayoutSection[];
};

export type Point = { x: number; y: number };
export type Box = { x: number; y: number; w: number; h: number };

export type PlacedSeat = {
  id: string;
  /** "G9" — unique per section. */
  label: string;
  n: number;
  row: string;
  section: string;
  tier: string;
  x: number;
  y: number;
  /** Index into `SeatIndex.rows`. */
  rowIndex: number;
};

export type PlacedRow = {
  section: string;
  label: string;
  /** Seat ids in seat-number order. */
  seats: string[];
  /** Load-motion stagger slot: rows pop in front to back (wedges ring outward together). */
  order: number;
  /** Where the row letter goes at each end (rows-shaped sections only). */
  ends: [Point, Point] | null;
};

export type PlacedSection = {
  key: string;
  label: string;
  tier: string;
  shape: "rows" | "wedge";
  polygon: Point[] | null;
  /** Seats' bounding box (plus the polygon for wedges). */
  box: Box;
  centre: Point;
  /** Indexes into `SeatIndex.rows`, front to back. */
  rows: number[];
};

export type SeatIndex = {
  layout: Layout;
  seats: PlacedSeat[];
  byId: Map<string, PlacedSeat>;
  rows: PlacedRow[];
  sections: PlacedSection[];
  /** Spatial hash: `"cx,cy"` (PITCH cells) → indexes into `seats`. */
  cells: Map<string, number[]>;
};

const cellKey = (x: number, y: number) => `${Math.floor(x / PITCH)},${Math.floor(y / PITCH)}`;

export function indexLayout(layout: Layout): SeatIndex {
  const seats: PlacedSeat[] = [];
  const byId = new Map<string, PlacedSeat>();
  const rows: PlacedRow[] = [];
  const sections: PlacedSection[] = [];
  const cells = new Map<string, number[]>();
  let order = 0; // rows-shaped sections stack front to back

  for (const s of layout.sections) {
    const rowIdx: number[] = [];
    const xs: number[] = [];
    const ys: number[] = [];
    s.rows.forEach((r, ri) => {
      const rowIndex = rows.length;
      const sorted = [...r.seats].sort((a, b) => a.n - b.n);
      for (const seat of sorted) {
        const placed: PlacedSeat = {
          id: seat.id,
          label: `${r.label}${seat.n}`,
          n: seat.n,
          row: r.label,
          section: s.key,
          tier: s.tier,
          x: seat.x,
          y: seat.y,
          rowIndex,
        };
        const key = cellKey(seat.x, seat.y);
        const bucket = cells.get(key);
        if (bucket) bucket.push(seats.length);
        else cells.set(key, [seats.length]);
        seats.push(placed);
        byId.set(seat.id, placed);
        xs.push(seat.x - SEAT / 2, seat.x + SEAT / 2);
        ys.push(seat.y - SEAT / 2, seat.y + SEAT / 2);
      }
      rows.push({
        section: s.key,
        label: r.label,
        seats: sorted.map((x) => x.id),
        order: s.shape === "wedge" ? ri : order + ri,
        ends: s.shape === "rows" ? rowEnds(sorted) : null,
      });
      rowIdx.push(rowIndex);
    });
    if (s.shape === "rows") order += s.rows.length;

    const polygon = s.polygon?.map(([x, y]) => ({ x, y })) ?? null;
    for (const p of polygon ?? []) {
      xs.push(p.x);
      ys.push(p.y);
    }
    const box = boundsOf(xs, ys);
    const centre = polygon ? centroid(polygon) : { x: box.x + box.w / 2, y: box.y + box.h / 2 };
    sections.push({ key: s.key, label: s.label, tier: s.tier, shape: s.shape, polygon, box, centre, rows: rowIdx });
  }
  return { layout, seats, byId, rows, sections, cells };
}

/** One PITCH past each end of the row, continuing the row's own direction (works on arcs). */
function rowEnds(seats: LayoutSeat[]): [Point, Point] | null {
  if (!seats.length) return null;
  const first = seats[0];
  const last = seats[seats.length - 1];
  if (seats.length === 1) return [{ x: first.x - PITCH, y: first.y }, { x: first.x + PITCH, y: first.y }];
  const out = (a: LayoutSeat, b: LayoutSeat): Point => {
    const dx = a.x - b.x;
    const dy = a.y - b.y;
    const len = Math.hypot(dx, dy) || 1;
    return { x: a.x + (dx / len) * PITCH, y: a.y + (dy / len) * PITCH };
  };
  return [out(first, seats[1]), out(last, seats[seats.length - 2])];
}

function boundsOf(xs: number[], ys: number[]): Box {
  if (!xs.length) return { x: 0, y: 0, w: 0, h: 0 };
  const x = Math.min(...xs);
  const y = Math.min(...ys);
  return { x, y, w: Math.max(...xs) - x, h: Math.max(...ys) - y };
}

function centroid(points: Point[]): Point {
  const sum = points.reduce((a, p) => ({ x: a.x + p.x, y: a.y + p.y }), { x: 0, y: 0 });
  return { x: sum.x / points.length, y: sum.y / points.length };
}

/** The whole layout as a box. */
export function layoutBox(layout: Layout): Box {
  return { x: 0, y: 0, w: layout.width, h: layout.height };
}

// --- hit-testing ----------------------------------------------------------------------------------

/**
 * The seat nearest to a layout point, if one is within `radius` of its centre. The default
 * (half a pitch) splits the gap between neighbours, so a slightly-off tap still lands.
 */
export function hitTest(index: SeatIndex, x: number, y: number, radius = PITCH / 2): string | null {
  const cx = Math.floor(x / PITCH);
  const cy = Math.floor(y / PITCH);
  let best: PlacedSeat | null = null;
  let bestD = radius * radius;
  for (let i = cx - 1; i <= cx + 1; i++)
    for (let j = cy - 1; j <= cy + 1; j++)
      for (const k of index.cells.get(`${i},${j}`) ?? []) {
        const s = index.seats[k];
        const d = (s.x - x) ** 2 + (s.y - y) ** 2;
        if (d <= bestD) {
          bestD = d;
          best = s;
        }
      }
  return best?.id ?? null;
}

function inPolygon(p: Point, poly: Point[]): boolean {
  let inside = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const a = poly[i];
    const b = poly[j];
    if (a.y > p.y !== b.y > p.y && p.x < ((b.x - a.x) * (p.y - a.y)) / (b.y - a.y) + a.x) inside = !inside;
  }
  return inside;
}

/** The section under a layout point: a wedge's polygon, else the section of a nearby seat. */
export function sectionAt(index: SeatIndex, x: number, y: number): string | null {
  for (const s of index.sections) if (s.polygon && inPolygon({ x, y }, s.polygon)) return s.key;
  const id = hitTest(index, x, y, PITCH * 1.5);
  if (id) return index.byId.get(id)!.section;
  for (const s of index.sections) {
    const b = s.box;
    if (x >= b.x && x <= b.x + b.w && y >= b.y && y <= b.y + b.h) return s.key;
  }
  return null;
}

// --- keyboard movement ----------------------------------------------------------------------------

export type Direction = "left" | "right" | "up" | "down" | "home" | "end";

/**
 * The seat an arrow key moves to. Left/right walk the row; up/down go to the nearest seat of the
 * row in front / behind — across into the next rows-section (stalls → balcony), but a wedge
 * keeps to itself. At an edge the seat stays where it is.
 */
export function neighbour(index: SeatIndex, id: string, dir: Direction): string {
  const seat = index.byId.get(id);
  if (!seat) return id;
  const row = index.rows[seat.rowIndex];
  const at = row.seats.indexOf(id);
  if (dir === "left") return row.seats[Math.max(0, at - 1)];
  if (dir === "right") return row.seats[Math.min(row.seats.length - 1, at + 1)];
  if (dir === "home") return row.seats[0];
  if (dir === "end") return row.seats[row.seats.length - 1];

  const section = index.sections.find((s) => s.key === seat.section)!;
  const step = dir === "up" ? -1 : 1;
  let target: PlacedRow | undefined;
  const pos = section.rows.indexOf(seat.rowIndex) + step;
  if (pos >= 0 && pos < section.rows.length) target = index.rows[section.rows[pos]];
  else if (section.shape === "rows") {
    const flow = index.sections.filter((s) => s.shape === "rows");
    const next = flow[flow.indexOf(section) + step];
    const r = next && (step < 0 ? next.rows[next.rows.length - 1] : next.rows[0]);
    if (r !== undefined) target = index.rows[r];
  }
  if (!target) return id;
  let best = target.seats[0];
  let bestD = Infinity;
  for (const other of target.seats) {
    const o = index.byId.get(other)!;
    const d = (o.x - seat.x) ** 2 + (o.y - seat.y) ** 2;
    if (d < bestD) {
      bestD = d;
      best = other;
    }
  }
  return best;
}

/** The seat to start keyboard focus on: the free seat nearest the middle of the front rows. */
export function startSeat(index: SeatIndex, isFree: (id: string) => boolean): string | null {
  const s = index.layout.stage;
  const target = { x: s.x + s.w / 2, y: s.y };
  let best: string | null = null;
  let bestD = Infinity;
  for (const seat of index.seats) {
    if (!isFree(seat.id)) continue;
    // Weight depth over offset so "front-centre" beats "dead centre, far back".
    const d = Math.abs(seat.x - target.x) + 2 * Math.abs(seat.y - target.y);
    if (d < bestD) {
      bestD = d;
      best = seat.id;
    }
  }
  return best ?? index.seats[0]?.id ?? null;
}

// --- live state (06 §D) ---------------------------------------------------------------------------

export type SeatStatus = "free" | "sold" | "held" | "mine";

/** `GET /showtimes/{id}/seats` (and the v2 stream's `snapshot`). */
export type SeatSnapshot = {
  v: number;
  server_time: string;
  sold: string[];
  held: { seat_id: string; expires_at: string }[];
  mine: string[];
};

/** The v2 stream's `diff`. */
export type SeatDiff = {
  v: number;
  held_add?: SeatSnapshot["held"];
  held_del?: string[];
  sold_add?: string[];
};

export type SeatState = {
  v: number;
  sold: ReadonlySet<string>;
  /** Someone else's holds: seat id → expires_at (ISO). */
  held: ReadonlyMap<string, string>;
  mine: ReadonlySet<string>;
};

export const EMPTY_STATE: SeatState = { v: -1, sold: new Set(), held: new Map(), mine: new Set() };

export function fromSnapshot(s: SeatSnapshot): SeatState {
  return {
    v: s.v,
    sold: new Set(s.sold),
    held: new Map(s.held.map((h) => [h.seat_id, h.expires_at])),
    mine: new Set(s.mine),
  };
}

/** A snapshot replaces the state unless it is older than what we have. */
export function mergeSnapshot(prev: SeatState, snap: SeatSnapshot): SeatState {
  return snap.v < prev.v ? prev : fromSnapshot(snap);
}

/**
 * Apply a diff. Stale (`v` ≤ current) → `prev` unchanged; a gap (`v` > current + 1) → `null`,
 * meaning a diff was missed and the caller should fetch a fresh snapshot.
 */
export function applyDiff(prev: SeatState, diff: SeatDiff): SeatState | null {
  if (diff.v <= prev.v) return prev;
  if (diff.v > prev.v + 1) return null;
  const sold = new Set(prev.sold);
  const held = new Map(prev.held);
  const mine = new Set(prev.mine);
  for (const id of diff.held_del ?? []) {
    held.delete(id);
    mine.delete(id);
  }
  for (const h of diff.held_add ?? []) if (!mine.has(h.seat_id)) held.set(h.seat_id, h.expires_at);
  for (const id of diff.sold_add ?? []) {
    sold.add(id);
    held.delete(id);
    mine.delete(id);
  }
  return { v: diff.v, sold, held, mine };
}

/** Sold beats held beats mine — a seat sold under you is sold. */
export function statusOf(state: SeatState, id: string): SeatStatus {
  if (state.sold.has(id)) return "sold";
  if (state.held.has(id)) return "held";
  if (state.mine.has(id)) return "mine";
  return "free";
}

/** Seat ids whose status differs between two states (for motion on change). */
export function changedSeats(a: SeatState, b: SeatState): string[] {
  const ids = new Set<string>([...a.sold, ...b.sold, ...a.held.keys(), ...b.held.keys(), ...a.mine, ...b.mine]);
  return [...ids].filter((id) => statusOf(a, id) !== statusOf(b, id));
}

// --- tiers ----------------------------------------------------------------------------------------

/** Brand tier colours (04-ui-mockups tokens), cheapest first. */
export type TierToken = "classic" | "mint" | "prime" | "recliner";

const PALETTES: Record<number, TierToken[]> = {
  1: ["prime"],
  2: ["classic", "prime"],
  3: ["classic", "prime", "recliner"],
  4: ["classic", "mint", "prime", "recliner"],
};

/**
 * Tier key → colour token. Ranked by price when prices are known (so the most expensive tier is
 * always recliner violet, whatever the template calls it), else by legend order.
 */
export function tierPalette(tiers: { key: string }[], prices?: Record<string, number>): Record<string, TierToken> {
  const keys = tiers.map((t) => t.key);
  if (prices) keys.sort((a, b) => (prices[a] ?? 0) - (prices[b] ?? 0));
  const palette = PALETTES[Math.min(Math.max(keys.length, 1), 4)];
  const out: Record<string, TierToken> = {};
  keys.forEach((k, i) => {
    out[k] = palette[Math.min(i, palette.length - 1)];
  });
  return out;
}
