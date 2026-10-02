"use client";

import { useState } from "react";
import type { SeatIndex } from "@/components/seat-map/core";
import type { SeatLook } from "@/components/seat-map/SeatMap";

/**
 * The map as a list, for screen readers: one checkbox per open seat, grouped by section and row.
 * Collapsed by default (a thousand hidden checkboxes would swamp the tab order); its toggle is
 * visually hidden until focused, like a skip link.
 */
export function SeatList({
  index,
  lookOf,
  onToggle,
  tierText,
}: {
  index: SeatIndex;
  lookOf: (id: string) => SeatLook;
  onToggle: (id: string) => void;
  tierText: Record<string, string>;
}) {
  const [open, setOpen] = useState(false);
  return (
    <div className={open ? "mt-4 rounded-card bg-plum-2 p-4" : undefined}>
      <button
        type="button"
        aria-expanded={open}
        aria-controls="seat-list"
        onClick={() => setOpen((o) => !o)}
        className={
          open
            ? "cursor-pointer text-sm font-semibold underline underline-offset-4"
            : "sr-only cursor-pointer focus:not-sr-only focus:mt-3 focus:inline-block focus:text-sm focus:underline"
        }
      >
        {open ? "Hide the seat list" : "Choose seats from a list instead of the map"}
      </button>
      {open && (
        <div id="seat-list" className="mt-3 grid max-h-[50vh] gap-4 overflow-y-auto">
          {index.sections.map((s) => (
            <section key={s.key} aria-label={`${s.label}, ${tierText[s.tier] ?? s.tier}`}>
              <h3 className="font-cond text-lg font-bold">
                {s.label} · {tierText[s.tier] ?? "not on sale"}
              </h3>
              {s.rows.map((ri) => {
                const row = index.rows[ri];
                const free = row.seats.filter((id) => {
                  const l = lookOf(id);
                  return l === "free" || l === "mine";
                });
                return (
                  <fieldset key={ri} className="mt-2 border-0 p-0">
                    <legend className="text-sm text-muted-foreground">
                      Row {row.label} · {free.length ? `${free.length} open` : "full"}
                    </legend>
                    <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-sm">
                      {free.map((id) => {
                        const seat = index.byId.get(id)!;
                        return (
                          <label key={id} className="inline-flex items-center gap-1">
                            <input type="checkbox" checked={lookOf(id) === "mine"} onChange={() => onToggle(id)} />
                            {seat.label}
                          </label>
                        );
                      })}
                    </div>
                  </fieldset>
                );
              })}
            </section>
          ))}
        </div>
      )}
    </div>
  );
}
