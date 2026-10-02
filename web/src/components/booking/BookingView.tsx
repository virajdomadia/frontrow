"use client";

import { useCallback, useMemo, useState } from "react";
import { FillBadge } from "@/components/events/badges";
import { fromSnapshot, indexLayout, statusOf, tierPalette, type PlacedSeat, type SeatIndex } from "@/components/seat-map/core";
import { SeatMap, type SeatLook } from "@/components/seat-map/SeatMap";
import { dayParts, rupees, showTime } from "@/lib/format";
import type { Layout, SeatSnapshot, ShowtimeDetail } from "@/lib/types";
import { Legend } from "./Legend";
import { SeatList } from "./SeatList";
import { Stub, type StubLine } from "./Stub";

export const MAX_SEATS = 10; // 06 §C: holds over ten → 422 too_many_seats

/** "C7", or "Sec 3 · C7" in an arena where every wedge has its own row A. */
export function seatName(index: SeatIndex, seat: PlacedSeat) {
  if (index.layout.template !== "arena") return seat.label;
  const section = index.sections.find((s) => s.key === seat.section);
  return `${section?.label.replace("Section", "Sec") ?? seat.section} · ${seat.label}`;
}

/**
 * S4: the map, its legend and the stub that fills as you pick. Selection is local in F1; F2 swaps
 * the fixed snapshot for `useSeatState` (polling) and turns each pick into a hold.
 */
export function BookingView({ showtime, layout, snapshot }: { showtime: ShowtimeDetail; layout: Layout; snapshot: SeatSnapshot }) {
  const index = useMemo(() => indexLayout(layout), [layout]);
  const [state] = useState(() => fromSnapshot(snapshot));
  const [selected, setSelected] = useState<string[]>([]);
  const [notice, setNotice] = useState("");

  const prices = useMemo(() => Object.fromEntries(showtime.tiers.map((t) => [t.tier_key, t.price_paise])), [showtime.tiers]);
  const palette = useMemo(() => tierPalette(layout.tiers, prices), [layout.tiers, prices]);
  const tierText = useMemo(
    () => Object.fromEntries(showtime.tiers.map((t) => [t.tier_key, `${t.label} ${rupees(t.price_paise)}`])),
    [showtime.tiers],
  );
  const chosen = useMemo(() => new Set(selected), [selected]);

  const lookOf = useCallback(
    (id: string): SeatLook => {
      const seat = index.byId.get(id);
      if (!seat || !(seat.tier in prices)) return "off";
      const status = statusOf(state, id);
      if (status !== "free") return status;
      return chosen.has(id) ? "mine" : "free";
    },
    [index, prices, state, chosen],
  );

  const toggle = useCallback(
    (id: string) => {
      const seat = index.byId.get(id);
      if (!seat) return;
      const name = seatName(index, seat);
      const look = lookOf(id);
      if (look === "mine") {
        setSelected((s) => s.filter((x) => x !== id));
        setNotice(`${name} removed`);
      } else if (look !== "free") {
        setNotice(`${name} is ${look === "off" ? "not on sale" : look === "held" ? "held by someone else" : "sold"}`);
      } else if (selected.length >= MAX_SEATS) {
        setNotice(`Up to ${MAX_SEATS} seats per booking`);
      } else {
        setSelected((s) => [...s, id]);
        setNotice(`${name} added`);
      }
    },
    [index, lookOf, selected.length],
  );

  // Picks in hall order (front to back, left to right), not tap order.
  const picks = index.seats.filter((s) => chosen.has(s.id));
  const lines: StubLine[] = showtime.tiers
    .map((t) => {
      const n = picks.filter((p) => p.tier === t.tier_key).length;
      return { label: `${n} × ${t.label}`, paise: n * t.price_paise, n };
    })
    .filter((l) => l.n > 0);
  const fee = picks.length * showtime.fee_paise;
  const total = lines.reduce((a, l) => a + l.paise, 0) + fee;
  const { weekday, date } = dayParts(showtime.starts_at);
  const venueShort = showtime.venue.name.replace("Orbit Cinemas · ", "");

  const stub = {
    title: showtime.event.title,
    venue: showtime.venue.name,
    date: `${weekday} ${date}`,
    time: showTime(showtime.starts_at),
    picks: picks.map((p) => ({ id: p.id, name: seatName(index, p) })),
    lines,
    fee,
    total,
    notice,
    onRemove: toggle,
  };

  return (
    <div className="mx-auto w-[min(1440px,100%)] lg:grid lg:h-[calc(100dvh-69px)] lg:grid-cols-[1fr_380px] lg:gap-2">
      <section aria-labelledby="book-title" className="flex min-h-0 flex-col px-4 pt-4 pb-[200px] lg:px-10 lg:pb-4">
        <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1">
          <h1 id="book-title" className="font-cond text-[26px] leading-none font-extrabold uppercase lg:text-[30px]">
            <span className="hidden lg:inline">{venueShort} · </span>
            {showtime.event.title}
          </h1>
          <p className="flex items-center gap-3 text-[13px] text-muted-foreground lg:text-sm">
            <span>
              {weekday} {date} · {showTime(showtime.starts_at)} · <span className="lg:hidden">{venueShort}</span>
              <span className="hidden lg:inline">{showtime.venue.name}</span>
            </span>
            {showtime.fill === "filling" && <FillBadge fill="filling" />}
          </p>
        </div>

        <SeatMap
          index={index}
          lookOf={lookOf}
          onToggle={toggle}
          palette={palette}
          tierText={tierText}
          className="mt-3 h-[440px] rounded-card border border-border bg-plum lg:h-auto lg:min-h-0 lg:flex-1 lg:border-0"
        />
        <p className="mt-1.5 text-[11px] text-faint lg:hidden">Drag to pan · pinch to zoom · tap a seat</p>
        <Legend tiers={showtime.tiers} palette={palette} />
        <SeatList index={index} lookOf={lookOf} onToggle={toggle} tierText={tierText} />
      </section>

      <Stub {...stub} />
    </div>
  );
}
