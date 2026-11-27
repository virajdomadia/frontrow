import type { TierToken } from "@/components/seat-map/core";
import { rupees } from "@/lib/format";
import type { TierPrice } from "@/lib/types";
import { cn } from "@/lib/utils";

const SWATCH: Record<TierToken, string> = {
  classic: "bg-classic",
  mint: "bg-mint",
  prime: "bg-prime",
  recliner: "bg-recliner",
};

/** Tier colours with this show's prices, then the three states. */
export function Legend({ tiers, palette }: { tiers: TierPrice[]; palette: Record<string, TierToken> }) {
  const chip = "inline-block size-3 rounded-[2px]";
  return (
    <ul className="mt-3 flex list-none flex-wrap gap-x-4 gap-y-1.5 p-0 text-[13px] text-ink-2">
      {tiers.map((t) => (
        <li key={t.tier_key} className="inline-flex items-center gap-1.5">
          <i aria-hidden="true" className={cn(chip, SWATCH[palette[t.tier_key] ?? "classic"])} />
          {t.label} <b className="font-cond text-[15px] font-bold text-screen">{rupees(t.price_paise)}</b>
        </li>
      ))}
      <li className="inline-flex items-center gap-1.5">
        <i aria-hidden="true" className={cn(chip, "bg-held")} />
        Held by someone
      </li>
      <li className="inline-flex items-center gap-1.5">
        <i aria-hidden="true" className={cn(chip, "grid size-3 place-items-center bg-plum-3 text-[10px] leading-none text-ink-3 outline outline-1 outline-screen/20")}>×</i>
        Sold
      </li>
      <li className="inline-flex items-center gap-1.5">
        <i aria-hidden="true" className={cn(chip, "bg-red")} />
        Yours
      </li>
    </ul>
  );
}
