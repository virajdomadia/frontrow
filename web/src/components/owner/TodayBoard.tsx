"use client";

import { useCallback, useEffect, useState } from "react";
import { FillBar, PageHead, Stat } from "@/components/owner/ui";
import { send } from "@/lib/client";
import { rupees, showTime } from "@/lib/format";
import type { OwnerShow, OwnerToday } from "@/lib/types";
import { cn } from "@/lib/utils";
import { ShowFloor } from "./ShowFloor";

const REFRESH_MS = 20_000;

/**
 * L3 · Today: every show today with its fill, today's tickets and revenue, and the latest
 * sales. The selected show's map is live (pushed); the totals refresh when that map changes,
 * after the owner acts, and every 20 s while the tab is visible (other shows' sales).
 */
export function TodayBoard({ initial, demo }: { initial: OwnerToday; demo: boolean }) {
  const [day, setDay] = useState(initial);
  const upcoming = (s: OwnerShow) => new Date(s.starts_at).getTime() > Date.now();
  const [picked, setPicked] = useState<string | null>(() => (initial.shows.find(upcoming) ?? initial.shows[0])?.id ?? null);

  const refresh = useCallback(async () => {
    try {
      setDay(await send<OwnerToday>("GET", "/owner/today"));
    } catch {
      // The board keeps what it has; the next tick tries again.
    }
  }, []);

  useEffect(() => {
    const t = window.setInterval(() => {
      if (document.visibilityState === "visible") void refresh();
    }, REFRESH_MS);
    return () => window.clearInterval(t);
  }, [refresh]);

  const show = day.shows.find((s) => s.id === picked) ?? null;
  const blocked = day.shows.reduce((a, s) => a + s.blocked, 0);

  return (
    <>
      <PageHead
        title="Today"
        sub={new Date(`${day.date}T00:00:00`).toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long" })}
      />
      <div className="mb-8 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Tickets sold" value={day.tickets} />
        <Stat label="Revenue" value={rupees(day.revenue_paise)} hint="Ticket sales, before the Frontrow fee" />
        <Stat label="Shows" value={day.shows.length} />
        <Stat label="Seats blocked" value={blocked} />
      </div>

      {day.shows.length === 0 ? (
        <p className="rounded-card border border-border bg-plum-2 px-5 py-6 text-ink-2">No shows today. Schedule some from Shows.</p>
      ) : (
        <div className="grid gap-6 lg:grid-cols-[340px_1fr]">
          <section aria-labelledby="today-shows">
            <h2 id="today-shows" className="mb-3 font-cond text-2xl font-bold uppercase">
              Shows
            </h2>
            <ul className="grid list-none gap-2 p-0">
              {day.shows.map((s) => (
                <li key={s.id}>
                  <button
                    type="button"
                    aria-pressed={s.id === picked}
                    onClick={() => setPicked(s.id)}
                    className={cn(
                      "grid w-full cursor-pointer gap-2 rounded-card border px-4 py-3 text-left transition-colors",
                      s.id === picked ? "border-ink bg-paper" : "border-border bg-plum-2 hover:border-ink/40",
                    )}
                  >
                    <span className="flex items-baseline justify-between gap-3">
                      <b className="font-cond text-xl font-bold">{showTime(s.starts_at)}</b>
                      <span className="text-xs text-muted-foreground">
                        {upcoming(s) ? s.screen_name : "Started"} · {s.cinema_name}
                      </span>
                    </span>
                    <span className="truncate text-sm font-semibold text-ink">
                      {s.film.title} <span className="font-normal text-muted-foreground">· {s.language} {s.format}</span>
                    </span>
                    <FillBar sold={s.sold} total={s.seat_count} />
                    {s.blocked > 0 && <span className="text-xs text-ink-2">{s.blocked} blocked</span>}
                  </button>
                </li>
              ))}
            </ul>
          </section>

          <div className="grid min-w-0 content-start gap-6">
            {show && <ShowFloor key={show.id} show={show} demo={demo} onChange={refresh} />}
            <section aria-labelledby="today-recent">
              <h2 id="today-recent" className="mb-3 font-cond text-2xl font-bold uppercase">
                Latest sales
              </h2>
              {day.recent.length === 0 ? (
                <p className="text-sm text-muted-foreground">No sales yet today.</p>
              ) : (
                <ul className="grid list-none divide-y divide-border rounded-card border border-border bg-plum-2 p-0">
                  {day.recent.map((r) => (
                    <li key={r.order_id} className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 px-4 py-2.5 text-sm">
                      <span>
                        <b className="font-semibold text-ink">{r.name}</b>{" "}
                        <span className="text-ink-2">
                          {r.seats} {r.seats === 1 ? "seat" : "seats"} · {r.film_title} {showTime(r.starts_at)}
                        </span>
                        {r.channel === "counter" && <span className="ml-2 text-xs font-semibold text-red-dark uppercase">Counter</span>}
                      </span>
                      <span className="tabular-nums text-ink">
                        {rupees(r.amount_paise)} <span className="text-xs text-muted-foreground">{showTime(r.paid_at)}</span>
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </div>
        </div>
      )}
    </>
  );
}
