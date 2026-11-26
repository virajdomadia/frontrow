import { cn } from "@/lib/utils";
import type { Cert, Fill } from "@/lib/types";

const base = "inline-block rounded-sm px-[7px] py-[3px] text-[11px] font-semibold tracking-[.06em] uppercase";

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
        fill === "filling" && "bg-amber/15 text-amber",
        fill === "available" && "bg-mint/15 text-[#1F6F58]",
        fill === "sold_out" && "bg-ink/10 text-ink-3",
        className,
      )}
    >
      {FILL_LABEL[fill]}
    </span>
  );
}

export const CERT_NOTE: Record<Cert, string> = {
  U: "Suitable for all ages",
  UA: "Parental guidance for children under 13",
  A: "Adults only (18+) — ID may be checked at the door",
};

/** The CBFC certificate as a square chip: U, UA, A. */
export function CertBadge({ cert, className }: { cert: Cert; className?: string }) {
  return (
    <span
      title={CERT_NOTE[cert]}
      className={cn(
        "inline-grid h-[22px] min-w-[26px] place-items-center rounded-sm border-[1.5px] px-1 font-cond text-[13px] leading-none font-bold",
        cert === "A" ? "border-red-dark text-red-dark" : "border-current",
        className,
      )}
    >
      {cert}
    </span>
  );
}
