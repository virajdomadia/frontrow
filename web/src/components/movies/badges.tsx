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
  "UA 7+": "Parental guidance for children under 7",
  "UA 13+": "Parental guidance for children under 13",
  "UA 16+": "Parental guidance for children under 16",
  A: "Adults only (18+) — ID may be checked at the door",
};

export const UNCERTIFIED_NOTE = "Not yet certified by the CBFC";

/** What a certificate means, or that the film has none yet. */
export function certNote(cert: Cert | null) {
  return cert ? CERT_NOTE[cert] : UNCERTIFIED_NOTE;
}

/** The CBFC certificate as a chip: U, UA 7+, UA 13+, UA 16+, A — or "TBC" before certification. */
export function CertBadge({ cert, className }: { cert: Cert | null; className?: string }) {
  return (
    <span
      title={certNote(cert)}
      className={cn(
        "inline-grid h-[22px] min-w-[26px] place-items-center rounded-sm border-[1.5px] px-1 font-cond text-[13px] leading-none font-bold whitespace-nowrap",
        cert === "A" ? "border-red-dark text-red-dark" : "border-current",
        cert === null && "border-dashed opacity-80",
        className,
      )}
    >
      {cert ?? "TBC"}
    </span>
  );
}
