"use client";

import Link from "next/link";
import { useRef, useState } from "react";
import { priceRange, showTime } from "@/lib/format";
import type { Fill } from "@/lib/types";
import { cn } from "@/lib/utils";
import { FILL_LABEL } from "./badges";

export type ShowtimeDay = {
  key: string;
  weekday: string;
  date: string;
  /** "Today" / "Tomorrow" when it applies. */
  relative?: string;
  venues: {
    id: string;
    name: string;
    detail: string;
    times: { id: string; startsAt: string; min: number; max: number; fill: Fill; seatsLeft: number }[];
  }[];
};

/** S3's showtime picker: a day strip (ARIA tabs, arrow keys) over venue cards of time chips. */
export function Showtimes({ days }: { days: ShowtimeDay[] }) {
  const [active, setActive] = useState(days[0]?.key);
  const tabs = useRef<(HTMLButtonElement | null)[]>([]);
  const day = days.find((d) => d.key === active) ?? days[0];

  if (!day)
    return (
      <p className="rounded-card bg-plum-2 px-5 py-4 text-muted-foreground">
        No upcoming showtimes right now — check back soon.
      </p>
    );

  function onKey(e: React.KeyboardEvent, i: number) {
    const step = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
    const to = e.key === "Home" ? 0 : e.key === "End" ? days.length - 1 : step ? (i + step + days.length) % days.length : -1;
    if (to < 0) return;
    e.preventDefault();
    setActive(days[to].key);
    tabs.current[to]?.focus();
  }

  return (
    <div>
      <div role="tablist" aria-label="Day" className="-mx-1 flex gap-2 overflow-x-auto px-1 pt-1 pb-2 [scrollbar-width:thin]">
        {days.map((d, i) => {
          const on = d.key === day.key;
          return (
            <button
              key={d.key}
              ref={(el) => {
                tabs.current[i] = el;
              }}
              role="tab"
              id={`day-${d.key}`}
              aria-selected={on}
              aria-controls="showtimes-panel"
              tabIndex={on ? 0 : -1}
              onClick={() => setActive(d.key)}
              onKeyDown={(e) => onKey(e, i)}
              className={cn(
                "grid shrink-0 cursor-pointer justify-items-start rounded-btn border px-3 py-1.5 text-left transition-colors",
                on ? "border-screen bg-screen text-plum" : "border-screen/20 text-muted-foreground hover:border-screen/50 hover:text-screen",
              )}
            >
              <span className="font-cond text-[17px] leading-tight font-bold tracking-[.04em] uppercase">
                {d.relative ?? d.weekday}
              </span>
              <span className={cn("text-xs", on ? "text-ink-2" : "text-faint")}>{d.date}</span>
            </button>
          );
        })}
      </div>

      <div role="tabpanel" id="showtimes-panel" aria-labelledby={`day-${day.key}`} className="mt-3 grid gap-3.5">
        {day.venues.map((v) => (
          <div
            key={v.id}
            className="grid gap-4 rounded-card bg-plum-2 px-5 py-4 md:grid-cols-[240px_1fr] md:items-center md:gap-5"
          >
            <div>
              <b className="block font-cond text-[22px] leading-tight font-bold">{v.name}</b>
              <p className="text-[13px] text-faint">{v.detail}</p>
            </div>
            <ul className="flex list-none flex-wrap gap-2 p-0">
              {v.times.map((t) => (
                <li key={t.id}>
                  <TimeChip t={t} />
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </div>
  );
}

function TimeChip({ t }: { t: ShowtimeDay["venues"][number]["times"][number] }) {
  const time = showTime(t.startsAt);
  if (t.fill === "sold_out")
    return (
      <span
        aria-disabled="true"
        className="block min-w-[104px] rounded-btn border border-screen/15 px-3 py-2 opacity-45"
      >
        <b className="block font-cond text-[19px] leading-tight font-bold tracking-[.03em] line-through">{time}</b>
        <span className="block text-[11px] text-muted-foreground">Sold out</span>
      </span>
    );
  const hot = t.fill === "filling";
  return (
    <Link
      href={`/book/${t.id}`}
      aria-label={`${time}, ${priceRange(t.min, t.max)}, ${FILL_LABEL[t.fill]}${hot ? `, ${t.seatsLeft} seats left` : ""}`}
      className={cn(
        "block min-w-[104px] rounded-btn border px-3 py-2 no-underline transition-colors hover:bg-plum-3",
        hot ? "border-amber" : "border-screen/25 hover:border-screen/60",
      )}
    >
      <b className="block font-cond text-[19px] leading-tight font-bold tracking-[.03em]">{time}</b>
      <span className={cn("block text-[11px]", hot ? "text-amber" : "text-muted-foreground")}>
        {priceRange(t.min, t.max)} · {hot ? `${t.seatsLeft} left` : FILL_LABEL[t.fill]}
      </span>
    </Link>
  );
}
