"use client";

import { useMemo } from "react";
import { indexLayout, tierPalette, type Layout } from "@/components/seat-map/core";
import { SeatMap } from "@/components/seat-map/SeatMap";
import { cn } from "@/lib/utils";

const SWATCH = { classic: "bg-classic", mint: "bg-mint", prime: "bg-prime", recliner: "bg-recliner" } as const;

/** The real `<SeatMap>` over a layout, every seat free — the venue preview (S10). */
export function LayoutPreview({ layout, className }: { layout: Layout; className?: string }) {
  const index = useMemo(() => indexLayout(layout), [layout]);
  const palette = useMemo(() => tierPalette(layout.tiers), [layout.tiers]);
  const tierText = useMemo(() => Object.fromEntries(layout.tiers.map((t) => [t.key, t.label])), [layout.tiers]);
  const counts = useMemo(() => {
    const out: Record<string, number> = {};
    for (const s of index.seats) out[s.tier] = (out[s.tier] ?? 0) + 1;
    return out;
  }, [index]);

  return (
    <div className="grid gap-2">
      <SeatMap
        // A new layout is a new map: remount so the camera refits.
        key={`${layout.width}x${layout.height}:${index.seats.length}`}
        index={index}
        lookOf={() => "free"}
        onToggle={() => {}}
        palette={palette}
        tierText={tierText}
        className={cn("h-[340px] rounded-card border border-border bg-plum sm:h-[420px]", className)}
      />
      <ul className="flex list-none flex-wrap gap-x-4 gap-y-1 p-0 text-xs text-muted-foreground">
        {layout.tiers.map((t) => (
          <li key={t.key} className="inline-flex items-center gap-1.5">
            <i aria-hidden="true" className={cn("inline-block size-2.5 rounded-[2px]", SWATCH[palette[t.key] ?? "classic"])} />
            {t.label} <b className="text-screen tabular-nums">{counts[t.key] ?? 0}</b>
          </li>
        ))}
      </ul>
    </div>
  );
}
