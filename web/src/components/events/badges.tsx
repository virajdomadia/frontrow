import { cn } from "@/lib/utils";
import type { EventCard, Fill } from "@/lib/types";

const base = "inline-block rounded-sm px-[7px] py-[3px] text-[11px] font-semibold tracking-[.06em] uppercase";

export function TypeBadge({ type }: { type: EventCard["type"] }) {
  return (
    <span className={cn(base, type === "movie" ? "bg-prime/15 text-prime" : "bg-recliner/20 text-recliner")}>
      {type === "movie" ? "Movie" : "Concert"}
    </span>
  );
}

export const FILL_LABEL: Record<Fill, string> = {
  available: "Available",
  filling: "Filling fast",
  sold_out: "Sold out",
};

export function FillBadge({ fill, className }: { fill: Fill; className?: string }) {
  return (
    <span
      className={cn(
        base,
        fill === "filling" && "bg-amber/20 text-amber",
        fill === "available" && "bg-classic/15 text-classic",
        fill === "sold_out" && "bg-screen/10 text-faint",
        className,
      )}
    >
      {FILL_LABEL[fill]}
    </span>
  );
}
