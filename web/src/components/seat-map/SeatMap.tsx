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
  seatLabel,
  sectionAt,
  sectionText,
  sectionStart,
  sectionStep,
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
  scaleOf,
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

const PHONE_PX = 768; // narrower panels start fitted to the hall's width, wider ones fit the hall
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
  /** Seats someone else just took or let go (L1): each gets one ripple. A new object replays. */
  ripple?: { ids: string[] } | null;
  /** A still camera: the whole hall, no pan / zoom / rail / hint, and the page scrolls over it
   *  (the landing page's small demo maps). */
  fixed?: boolean;
  /** Names the map for screen readers when a page has two ("Seat map" otherwise). */
  label?: string;
  className?: string;
};

/**
 * S4's map: SVG from the `Layout`, a camera (`viewbox.ts`) for pan / pinch / wheel / wedge zoom,
 * taps resolved by `core.hitTest`, and roving keyboard focus across the seats. The camera lives
 * in a ref and is written straight to the `viewBox` attribute, so a drag never re-renders rows.
 *
 * The zoom buttons sit in their own rail beside the map, never over seats, and one hint line
 * under it says what a tap does in the current view. In the arena overview each section is a
 * focusable button (Enter zooms in and puts focus on a seat there); Page Up / Page Down jump
 * between sections from any seat.
 */
export function SeatMap({ index, lookOf, onToggle, palette, tierText, ripple, fixed, label = "Seat map", className }: Props) {
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
  /** The arena section under the middle of a zoomed view — named under the map. */
  const [here, setHere] = useState<string | null>(null);
  const [focusId, setFocusId] = useState<string | null>(() => startSeat(index, (id) => lookOf(id) === "free"));

  const isArena = layout.template === "arena";

  const apply = useCallback(
    (next: Box) => {
      const v = view.current;
      if (!v) return;
      box.current = next;
      svg.current?.setAttribute("viewBox", `${next.x} ${next.y} ${next.w} ${next.h}`);
      const px = seatPx(next, v);
      setOverview(!fixed && px < OVERVIEW_PX); // a still map never turns taps into zooms
      setZoomed(px > seatPx(fit(content, v), v) * 1.05);
      setHere(isArena && px >= OVERVIEW_PX ? sectionAt(index, next.x + next.w / 2, next.y + next.h / 2) : null);
    },
    [content.w, content.h, index, isArena],
  );

  const home = useCallback((): Box => {
    const v = view.current!;
    const whole = clamp(fit(content, v, fixed ? 0 : PITCH / 2), content, v); // fixed: the layout margin is enough
    if (fixed || isArena || v.w >= PHONE_PX) return whole;
    // Phone: seats start at a fair tap size (≥ 24 px), centred, screen end at the top; pan for
    // the rest. A hall narrow enough to fit at that size shows whole (review 2026-11-27: 11 px
    // seats in a whole-hall overview were too small to hit).
    const scale = Math.max(v.w / (content.w + PITCH), MIN_TAP_PX / SEAT);
    if (scale <= scaleOf(whole, v)) return whole;
    const b = boxAt({ x: content.w / 2, y: 0 }, scale, v);
    return clamp({ ...b, y: 0 }, content, v);
  }, [content.w, content.h, isArena, fixed]);

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
    if (!fixed && seatPx(box.current, v) < OVERVIEW_PX) {
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
      if (g.moved && !fixed) apply(clamp(panBy(box.current, v, cur.x - prev.x, cur.y - prev.y), content, v));
      return;
    }
    if (fixed) return;
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
    if (!el || fixed) return; // a still map must not swallow the page's scroll
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
  }, [apply, fixed]);

  // --- keyboard: one tab stop, arrows rove, Enter/Space toggles -----------------------------------
  const reveal = useCallback(
    (id: string) => {
      const seat = index.byId.get(id);
      const v = view.current;
      if (!seat || !v || fixed) return; // a still map shows every seat already
      if (seatPx(box.current, v) < OVERVIEW_PX) {
        zoomToSection(seat.section);
        return;
      }
      const next = clamp(ensureVisible(box.current, seat, PITCH * 1.5), content, v);
      if (next !== box.current) moveTo(next);
    },
    [index, zoomToSection, moveTo, fixed],
  );

  const onKeyDown = (e: React.KeyboardEvent) => {
    const dir = KEYS[e.key];
    if (dir && focusId) {
      e.preventDefault();
      const next = neighbour(index, focusId, dir);
      focusSeat(next);
      reveal(next);
    } else if ((e.key === "PageDown" || e.key === "PageUp") && focusId) {
      e.preventDefault();
      const next = sectionStep(index, focusId, e.key === "PageDown" ? 1 : -1, isFree);
      focusSeat(next);
      reveal(next);
    } else if ((e.key === "Enter" || e.key === " ") && focusId) {
      e.preventDefault();
      onToggle(focusId);
    } else if (!fixed && (e.key === "+" || e.key === "=")) zoomBy(1.4);
    else if (!fixed && e.key === "-") zoomBy(1 / 1.4);
    else if (e.key === "Escape" && zoomed) moveTo(home());
  };

  const onFocus = (e: React.FocusEvent) => {
    const id = (e.target as Element).getAttribute("data-id");
    if (id) {
      setFocusId(id);
      reveal(id);
    }
  };

  const isFree = (id: string) => lookOf(id) === "free";

  // Straight on the DOM, so a ripple never re-renders a row; React keeps the seat's own classes.
  useEffect(() => {
    for (const id of ripple?.ids ?? []) {
      const el = svg.current?.querySelector<SVGElement>(`[data-id="${id}"]`);
      if (!el) continue;
      el.classList.remove("sm-ripple");
      void el.getBoundingClientRect(); // restart the animation if it is still running
      el.classList.add("sm-ripple");
      el.addEventListener("animationend", () => el.classList.remove("sm-ripple"), { once: true });
    }
  }, [ripple]);

  // Focusing the seat is enough: `onFocus` reveals it, which zooms into its section if needed.
  const focusSeat = (id: string) => {
    setFocusId(id);
    svg.current?.querySelector<SVGElement>(`[data-id="${id}"]`)?.focus({ preventScroll: true });
  };

  /** An overview section button: Enter / Space zooms in and lands on a seat there. */
  const onSectionKey = (e: React.KeyboardEvent, key: string) => {
    if (e.key !== "Enter" && e.key !== " ") return;
    e.preventDefault();
    e.stopPropagation(); // not the seat-map handler: that would toggle the roving seat
    const id = sectionStart(index, key, isFree);
    if (id) focusSeat(id);
    else zoomToSection(key);
  };

  const stage = layout.stage;
  const stageCx = stage.x + stage.w / 2;

  const sectionName = (key: string) => {
    const s = index.sections.find((x) => x.key === key);
    return s ? sectionText(s.label, tierText[s.tier]) : key;
  };
  const hereSection = here ? index.sections.find((s) => s.key === here) : null;

  return (
    <>
      <div className={cn("flex overflow-hidden", className)}>
        <div className="relative min-w-0 flex-1 overflow-hidden">
          <div
            ref={wrap}
            className={cn("sm-wrap absolute inset-0 select-none", fixed ? "touch-pan-y" : "touch-none")}
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
              aria-label={
                isArena
                  ? `${label}. Arrow keys move between seats, Page Up and Page Down jump between sections, Enter selects.`
                  : `${label}. Arrow keys move between seats, Enter selects.`
              }
              onKeyDown={onKeyDown}
              onFocus={onFocus}
            >
              <defs>
                <pattern id="sm-sold" width="1" height="1" patternContentUnits="objectBoundingBox">
                  <rect width="1" height="1" fill="var(--plum-3)" />
                  <path d="M.3 .3L.7 .7M.7 .3L.3 .7" stroke="var(--ink-3)" strokeWidth=".09" strokeLinecap="round" />
                </pattern>
              </defs>
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

              {/* Arena sections: in the overview each is a button (tap or Enter zooms in). Taps
                  go through the pointer handlers above, so there is no onClick here. */}
              {isArena &&
                index.sections.map((s) => (
                  <g
                    key={s.key}
                    role={overview ? "button" : undefined}
                    tabIndex={overview ? 0 : undefined}
                    aria-hidden={overview ? undefined : true}
                    aria-label={overview ? `${sectionName(s.key)}. Zoom in to pick seats` : undefined}
                    onKeyDown={overview ? (e) => onSectionKey(e, s.key) : undefined}
                    className={cn("sm-section", `t-${palette[s.tier]}`)}
                  >
                    {s.polygon ? (
                      <polygon points={s.polygon.map((p) => `${p.x},${p.y}`).join(" ")} />
                    ) : (
                      <rect x={s.box.x - 10} y={s.box.y - 10} width={s.box.w + 20} height={s.box.h + 20} rx={18} />
                    )}
                  </g>
                ))}

              {index.rows.map((row, i) => {
                const section = index.sections.find((s) => s.key === row.section);
                return (
                  <Row
                    key={i}
                    row={row}
                    index={index}
                    looks={row.seats.map((id) => CODE[lookOf(id)]).join("")}
                    focusId={focusId && index.byId.get(focusId)?.rowIndex === i ? focusId : null}
                    token={palette[index.byId.get(row.seats[0])?.tier ?? ""] ?? "classic"}
                    tierText={tierText}
                    section={isArena ? (section?.label ?? null) : null}
                    tags={section?.shape === "wedge"}
                  />
                );
              })}

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
        </div>

        {/* The controls' own rail: they never sit on top of a seat. */}
        <div hidden={fixed} className="flex w-12 shrink-0 flex-col items-center gap-1.5 border-l border-screen/10 py-2">
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
      </div>

      {/* One hint, for the view on screen. */}
      <p hidden={fixed} className="mt-1.5 flex flex-wrap gap-x-3 text-xs text-ink-3">
        {hereSection && (
          <span className="font-semibold text-muted-foreground">
            {sectionName(hereSection.key)} · row A nearest the {hereSection.shape === "wedge" ? "floor" : "stage"}
          </span>
        )}
        {overview ? (
          <span>{isArena ? "Tap a section to zoom in" : "Tap a block of seats to zoom in"}</span>
        ) : (
          <>
            <span className="lg:hidden">Drag to pan · pinch to zoom · tap a seat</span>
            <span className="hidden lg:inline">Drag to pan · scroll to zoom · click a seat</span>
          </>
        )}
      </p>
    </>
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
  /** The arena section's label, for seat names ("Section 3, B4, …"); null elsewhere. */
  section: string | null;
  /** Wedge rows: the row letter is drawn on the end seats (there is no room past them). */
  tags: boolean;
};

/** One row = one `<g>`, the unit of the load motion (`--i` staggers it). */
const Row = memo(
  function Row({ row, index, looks, focusId, token, tierText, section, tags }: RowProps) {
    const half = SEAT / 2;
    const last = row.seats.length - 1;
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
              aria-label={seatLabel(section, seat.label, tierText[seat.tier] ?? seat.tier, STATUS_TEXT[look])}
              className={cn("sm-seat", `t-${token}`, look)}
            />
          );
        })}
        {tags &&
          [0, last].filter((k, i, a) => a.indexOf(k) === i).map((k) => {
            const seat = index.byId.get(row.seats[k])!;
            const look = LOOK[looks[k]];
            return (
              <text key={k} x={seat.x} y={seat.y} aria-hidden="true" className={cn("sm-seat-tag", look !== "free" && look !== "sold" && "on-dark")}>
                {row.label}
              </text>
            );
          })}
      </g>
    );
  },
  (a, b) =>
    a.looks === b.looks && a.focusId === b.focusId && a.row === b.row && a.token === b.token && a.tierText === b.tierText,
);
