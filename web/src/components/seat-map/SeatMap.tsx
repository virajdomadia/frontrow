"use client";

import { Maximize2, Minus, Plus, Undo2 } from "lucide-react";
import { memo, useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";
import {
  hitTest,
  layoutBox,
  neighbour,
  PITCH,
  SEAT,
  sectionAt,
  startSeat,
  type Box,
  type Direction,
  type PlacedRow,
  type SeatIndex,
  type SeatStatus,
  type TierToken,
} from "./core";
import {
  animate,
  boxAt,
  clamp,
  ensureVisible,
  fit,
  focus,
  MIN_TAP_PX,
  OVERVIEW_PX,
  panBy,
  resize,
  seatPx,
  toLayout,
  zoomAt,
  type Size,
} from "./viewbox";

/** What the map draws per seat: the live status, or `off` for a tier this show doesn't sell. */
export type SeatLook = SeatStatus | "off";

const STATUS_TEXT: Record<SeatLook, string> = {
  free: "available",
  mine: "selected",
  held: "held by someone else",
  sold: "sold",
  off: "not on sale",
};

// Rows are memoised on a one-letter-per-seat string, so a toggle re-renders one row.
const CODE: Record<SeatLook, string> = { free: "f", mine: "m", held: "h", sold: "s", off: "o" };
const LOOK: Record<string, SeatLook> = { f: "free", m: "mine", h: "held", s: "sold", o: "off" };

const KEYS: Record<string, Direction> = {
  ArrowLeft: "left",
  ArrowRight: "right",
  ArrowUp: "up",
  ArrowDown: "down",
  Home: "home",
  End: "end",
};

const PHONE_PX = 768; // narrower panels start at tap size and pan, wider ones fit the hall
const TAP_SLOP = 6;
const ZOOM_MS = 450;

type Props = {
  index: SeatIndex;
  /** Per-seat look; `mine` already merges the local selection. */
  lookOf: (id: string) => SeatLook;
  onToggle: (id: string) => void;
  palette: Record<string, TierToken>;
  /** "Prime ₹320" per tier key — for seat labels. */
  tierText: Record<string, string>;
  className?: string;
};

/**
 * S4's map: SVG from the `Layout`, a camera (`viewbox.ts`) for pan / pinch / wheel / wedge zoom,
 * taps resolved by `core.hitTest`, and roving keyboard focus across the seats. The camera lives
 * in a ref and is written straight to the `viewBox` attribute, so a drag never re-renders rows.
 */
export function SeatMap({ index, lookOf, onToggle, palette, tierText, className }: Props) {
  const { layout } = index;
  const content = layoutBox(layout);
  const wrap = useRef<HTMLDivElement>(null);
  const svg = useRef<SVGSVGElement>(null);
  const view = useRef<Size | null>(null);
  const box = useRef<Box>(content);
  const cancelTween = useRef<() => void>(() => {});
  const reduced = useRef(false);
  const [overview, setOverview] = useState(false);
  const [zoomed, setZoomed] = useState(false);
  const [focusId, setFocusId] = useState<string | null>(() => startSeat(index, (id) => lookOf(id) === "free"));

  const isArena = layout.template === "arena";

  const apply = useCallback(
    (next: Box) => {
      const v = view.current;
      if (!v) return;
      box.current = next;
      svg.current?.setAttribute("viewBox", `${next.x} ${next.y} ${next.w} ${next.h}`);
      const px = seatPx(next, v);
      setOverview(px < OVERVIEW_PX);
      setZoomed(px > seatPx(fit(content, v), v) * 1.05);
    },
    [content.w, content.h],
  );

  const home = useCallback((): Box => {
    const v = view.current!;
    const whole = clamp(fit(content, v, PITCH / 2), content, v);
    if (isArena || v.w >= PHONE_PX || seatPx(whole, v) >= MIN_TAP_PX) return whole;
    // Phone: seats at full size, the screen end in view, centred — pan for the rest.
    const b = boxAt({ x: content.w / 2, y: 0 }, 1, v);
    return clamp({ ...b, y: 0 }, content, v);
  }, [content.w, content.h, isArena]);

  const moveTo = useCallback(
    (target: Box) => {
      cancelTween.current();
      cancelTween.current = animate(box.current, target, reduced.current ? 0 : ZOOM_MS, apply);
    },
    [apply],
  );

  // Measure the panel; keep the camera's aspect equal to it.
  useLayoutEffect(() => {
    const el = wrap.current;
    if (!el) return;
    reduced.current = matchMedia("(prefers-reduced-motion: reduce)").matches;
    const measure = () => {
      const next = { w: el.clientWidth, h: el.clientHeight };
      if (!next.w || !next.h) return;
      const prev = view.current;
      view.current = next;
      apply(prev ? clamp(resize(box.current, prev, next), content, next) : home());
    };
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => {
      ro.disconnect();
      cancelTween.current();
    };
  }, [apply, home]);

  const zoomToSection = useCallback(
    (key: string) => {
      const s = index.sections.find((x) => x.key === key);
      const v = view.current;
      if (!s || !v) return;
      moveTo(clamp(focus(s.box, v, MIN_TAP_PX / SEAT, PITCH / 2), content, v));
    },
    [index, moveTo],
  );

  const zoomBy = (factor: number) => {
    const v = view.current;
    if (!v) return;
    moveTo(clamp(zoomAt(box.current, v, factor, v.w / 2, v.h / 2), content, v));
  };

  const tap = (px: number, py: number) => {
    const v = view.current;
    if (!v) return;
    const p = toLayout(box.current, v, px, py);
    if (seatPx(box.current, v) < OVERVIEW_PX) {
      const key = sectionAt(index, p.x, p.y);
      if (key) zoomToSection(key);
      return;
    }
    const id = hitTest(index, p.x, p.y);
    if (id) {
      setFocusId(id);
      onToggle(id);
    }
  };

  // --- pointer gestures: drag to pan, two fingers to pinch, a still press is a tap -------------
  const pointers = useRef(new Map<number, { x: number; y: number }>());
  const gesture = useRef({ moved: false, sx: 0, sy: 0 });

  const local = (e: React.PointerEvent) => {
    const r = wrap.current!.getBoundingClientRect();
    return { x: e.clientX - r.left, y: e.clientY - r.top };
  };

  const onPointerDown = (e: React.PointerEvent) => {
    if (e.button !== 0) return;
    cancelTween.current();
    wrap.current?.setPointerCapture(e.pointerId);
    const p = local(e);
    pointers.current.set(e.pointerId, p);
    if (pointers.current.size === 1) gesture.current = { moved: false, sx: p.x, sy: p.y };
    else gesture.current.moved = true; // a second finger: this is a pinch, never a tap
  };

  const onPointerMove = (e: React.PointerEvent) => {
    const ps = pointers.current;
    const prev = ps.get(e.pointerId);
    const v = view.current;
    if (!prev || !v) return;
    const cur = local(e);
    if (ps.size === 1) {
      const g = gesture.current;
      if (!g.moved && Math.hypot(cur.x - g.sx, cur.y - g.sy) > TAP_SLOP) g.moved = true;
      ps.set(e.pointerId, cur);
      if (g.moved) apply(clamp(panBy(box.current, v, cur.x - prev.x, cur.y - prev.y), content, v));
      return;
    }
    const [a, b] = [...ps.entries()].slice(0, 2);
    const other = a[0] === e.pointerId ? b[1] : a[1];
    ps.set(e.pointerId, cur);
    const d0 = Math.hypot(prev.x - other.x, prev.y - other.y) || 1;
    const d1 = Math.hypot(cur.x - other.x, cur.y - other.y) || 1;
    const m0 = { x: (prev.x + other.x) / 2, y: (prev.y + other.y) / 2 };
    const m1 = { x: (cur.x + other.x) / 2, y: (cur.y + other.y) / 2 };
    const zoomedBox = zoomAt(box.current, v, d1 / d0, m1.x, m1.y);
    apply(clamp(panBy(zoomedBox, v, m1.x - m0.x, m1.y - m0.y), content, v));
  };

  const onPointerUp = (e: React.PointerEvent) => {
    const ps = pointers.current;
    if (!ps.has(e.pointerId)) return;
    const single = ps.size === 1;
    ps.delete(e.pointerId);
    if (single && !gesture.current.moved && e.type === "pointerup") {
      const p = local(e);
      tap(p.x, p.y);
    }
  };

  // Wheel / trackpad pinch zooms at the cursor (non-passive, so the page doesn't scroll).
  useEffect(() => {
    const el = wrap.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      const v = view.current;
      if (!v) return;
      e.preventDefault();
      cancelTween.current();
      const r = el.getBoundingClientRect();
      const factor = Math.exp(-e.deltaY * (e.ctrlKey ? 0.01 : 0.0015));
      apply(clamp(zoomAt(box.current, v, factor, e.clientX - r.left, e.clientY - r.top), content, v));
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, [apply]);

  // --- keyboard: one tab stop, arrows rove, Enter/Space toggles -----------------------------------
  const reveal = useCallback(
    (id: string) => {
      const seat = index.byId.get(id);
      const v = view.current;
      if (!seat || !v) return;
      if (seatPx(box.current, v) < OVERVIEW_PX) {
        zoomToSection(seat.section);
        return;
      }
      const next = clamp(ensureVisible(box.current, seat, PITCH * 1.5), content, v);
      if (next !== box.current) moveTo(next);
    },
    [index, zoomToSection, moveTo],
  );

  const onKeyDown = (e: React.KeyboardEvent) => {
    const dir = KEYS[e.key];
    if (dir && focusId) {
      e.preventDefault();
      const next = neighbour(index, focusId, dir);
      setFocusId(next);
      svg.current?.querySelector<SVGElement>(`[data-id="${next}"]`)?.focus({ preventScroll: true });
      reveal(next);
    } else if ((e.key === "Enter" || e.key === " ") && focusId) {
      e.preventDefault();
      onToggle(focusId);
    } else if (e.key === "+" || e.key === "=") zoomBy(1.4);
    else if (e.key === "-") zoomBy(1 / 1.4);
    else if (e.key === "Escape" && zoomed) moveTo(home());
  };

  const onFocus = (e: React.FocusEvent) => {
    const id = (e.target as Element).getAttribute("data-id");
    if (id) {
      setFocusId(id);
      reveal(id);
    }
  };

  const stage = layout.stage;
  const stageCx = stage.x + stage.w / 2;

  return (
    <div className={cn("relative overflow-hidden", className)}>
      <div
        ref={wrap}
        className="sm-wrap absolute inset-0 touch-none select-none"
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
      >
        <svg
          ref={svg}
          viewBox={`0 0 ${layout.width} ${layout.height}`}
          preserveAspectRatio="xMidYMid meet"
          className={cn("sm-map block size-full", overview && "is-overview")}
          role="group"
          aria-roledescription="seat map"
          aria-label="Seat map. Arrow keys move between seats, Enter selects."
          onKeyDown={onKeyDown}
          onFocus={onFocus}
        >
          {isArena ? (
            <g aria-hidden="true">
              <rect x={stage.x} y={stage.y - 12} width={stage.w} height={36} rx={6} className="sm-stage-block" />
              <text x={stageCx} y={stage.y + 6} className="sm-stage-label on-block">
                {stage.label}
              </text>
            </g>
          ) : (
            <g aria-hidden="true">
              <path
                d={`M ${stage.x} ${stage.y + 18} Q ${stageCx} ${stage.y - 8} ${stage.x + stage.w} ${stage.y + 18}`}
                className="sm-stage-arc"
              />
              <text x={stageCx} y={stage.y + 38} className="sm-stage-label">
                {stage.label}
              </text>
            </g>
          )}

          {isArena &&
            index.sections.map((s) => (
              <g key={s.key} aria-hidden="true" className={cn("sm-section", `t-${palette[s.tier]}`)}>
                {s.polygon ? (
                  <polygon points={s.polygon.map((p) => `${p.x},${p.y}`).join(" ")} />
                ) : (
                  <rect x={s.box.x - 10} y={s.box.y - 10} width={s.box.w + 20} height={s.box.h + 20} rx={18} />
                )}
              </g>
            ))}

          {index.rows.map((row, i) => (
            <Row
              key={i}
              row={row}
              index={index}
              looks={row.seats.map((id) => CODE[lookOf(id)]).join("")}
              focusId={focusId && index.byId.get(focusId)?.rowIndex === i ? focusId : null}
              token={palette[index.byId.get(row.seats[0])?.tier ?? ""] ?? "classic"}
              tierText={tierText}
              prefix={isArena ? `${index.sections.find((s) => s.key === row.section)?.label}, ` : ""}
            />
          ))}

          {/* Section numbers sit above the seats; they only show in the overview. */}
          {isArena && (
            <g aria-hidden="true">
              {index.sections.map((s) => (
                <text key={s.key} x={s.centre.x} y={s.centre.y} className="sm-section-label">
                  {s.label.replace("Section ", "")}
                </text>
              ))}
            </g>
          )}
        </svg>
      </div>

      <div className="absolute top-2 right-2 flex flex-col gap-1.5">
        <MapButton label="Zoom in" onClick={() => zoomBy(1.4)}>
          <Plus />
        </MapButton>
        <MapButton label="Zoom out" onClick={() => zoomBy(1 / 1.4)}>
          <Minus />
        </MapButton>
        {zoomed && (
          <MapButton label={isArena ? "All sections" : "Fit the hall"} onClick={() => moveTo(home())}>
            {isArena ? <Undo2 /> : <Maximize2 />}
          </MapButton>
        )}
      </div>
      {overview && (
        <p className="pointer-events-none absolute bottom-2 left-1/2 -translate-x-1/2 rounded-sm bg-plum/85 px-2.5 py-1 text-xs text-faint">
          Tap a section to pick seats
        </p>
      )}
    </div>
  );
}

function MapButton({ label, onClick, children }: { label: string; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      onClick={onClick}
      className="grid size-9 cursor-pointer place-items-center rounded-btn border border-screen/20 bg-plum/90 text-screen transition-colors hover:border-screen/60 [&_svg]:size-4"
    >
      {children}
    </button>
  );
}

type RowProps = {
  row: PlacedRow;
  index: SeatIndex;
  looks: string;
  focusId: string | null;
  token: TierToken;
  tierText: Record<string, string>;
  prefix: string;
};

/** One row = one `<g>`, the unit of the load motion (`--i` staggers it). */
const Row = memo(
  function Row({ row, index, looks, focusId, token, tierText, prefix }: RowProps) {
    const half = SEAT / 2;
    return (
      <g className="sm-row" style={{ "--i": row.order } as React.CSSProperties}>
        {row.ends?.map((p, k) => (
          <text key={k} x={p.x} y={p.y} className="sm-row-label" aria-hidden="true">
            {row.label}
          </text>
        ))}
        {row.seats.map((id, k) => {
          const seat = index.byId.get(id)!;
          const look = LOOK[looks[k]];
          return (
            <rect
              key={id}
              data-id={id}
              x={seat.x - half}
              y={seat.y - half}
              width={SEAT}
              height={SEAT}
              rx={3}
              tabIndex={id === focusId ? 0 : -1}
              role="button"
              aria-pressed={look === "mine"}
              aria-disabled={look !== "free" && look !== "mine"}
              aria-label={`${prefix}${seat.label}, ${tierText[seat.tier] ?? seat.tier}, ${STATUS_TEXT[look]}`}
              className={cn("sm-seat", `t-${token}`, look)}
            />
          );
        })}
      </g>
    );
  },
  (a, b) =>
    a.looks === b.looks && a.focusId === b.focusId && a.row === b.row && a.token === b.token && a.tierText === b.tierText,
);
