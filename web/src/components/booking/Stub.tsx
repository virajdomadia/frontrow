import { X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { rupees } from "@/lib/format";
import { cn } from "@/lib/utils";

export type StubLine = { label: string; paise: number; n: number };

type Props = {
  title: string;
  venue: string;
  date: string;
  time: string;
  picks: { id: string; name: string }[];
  lines: StubLine[];
  fee: number;
  total: number;
  /** Last pick/limit message — announced, and shown when it's a warning. */
  notice: string;
  onRemove: (id: string) => void;
  /** The hold countdown, "mm:ss" (10:00 until the first hold). */
  clock: string;
  /** A hold is running. */
  holding: boolean;
  /** Hold requests still in flight. */
  busy: boolean;
  proceeding: boolean;
  onProceed: () => void;
};

const HOLD_COPY = "Seats hold for 10 minutes once you pick them";
const HELD_COPY = "Held for you — pay before the clock runs out";

/**
 * The cream ticket stub (direction B). Desktop: a paper card beside the map that fills as you
 * pick. Phone: the same content as a bottom sheet — the sticky running total.
 */
export function Stub(p: Props) {
  const n = p.picks.length;
  const warn =
    p.notice.startsWith("Up to") ||
    / is (sold|held|not on sale)/.test(p.notice) ||
    /taken|ended|up —|Couldn't|unavailable|closed|Too many/.test(p.notice);
  const cta = p.proceeding ? "Starting checkout…" : n ? `Proceed to pay ${rupees(p.total)}` : "Pick seats to continue";
  const hint = p.holding ? HELD_COPY : HOLD_COPY;
  return (
    <>
      <p aria-live="polite" className="sr-only">
        {p.notice}
        {p.notice && n ? `. ${n} ${n === 1 ? "seat" : "seats"}, ${rupees(p.total)}` : ""}
      </p>

      {/* desktop stub */}
      <aside aria-label="Your booking" className="sm-stub hidden py-6 pr-6 lg:block">
        <div className="relative flex h-full flex-col rounded-card bg-paper text-ink border border-border shadow-[0_20px_50px_rgb(42_11_30_/_.16)]">
          <div className="relative border-b-2 border-dashed border-ink/25 px-6 pt-5.5 pb-4 before:absolute before:-bottom-[11px] before:-left-[11px] before:size-[22px] before:rounded-full before:bg-plum after:absolute after:-right-[11px] after:-bottom-[11px] after:size-[22px] after:rounded-full after:bg-plum">
            <h2 className="pr-16 font-cond text-[34px] leading-[.95] font-extrabold uppercase">{p.title}</h2>
            <p className="mt-1 text-sm font-medium text-ink-2">{p.venue}</p>
            <span className="absolute top-5.5 right-6 rotate-[-6deg] rounded-sm border-2 border-red-dark px-2.5 py-1.5 font-cond text-sm font-extrabold tracking-[.14em] text-red-dark uppercase">
              Admit
            </span>
          </div>

          <div className="grid flex-1 content-start gap-4 overflow-y-auto px-6 py-4.5">
            <div className="grid grid-cols-2 gap-3 text-[13px] text-ink-2">
              <div>
                Date<b className="block font-cond text-[22px] font-bold tracking-[.02em] text-ink">{p.date}</b>
              </div>
              <div>
                Show<b className="block font-cond text-[22px] font-bold tracking-[.02em] text-ink">{p.time}</b>
              </div>
            </div>

            <div>
              <div className="mb-1.5 text-[13px] text-ink-2">Seats {n > 0 && <span>· {n} of 10</span>}</div>
              {n ? (
                <Picks picks={p.picks} onRemove={p.onRemove} />
              ) : (
                <p className="text-sm text-ink-3">Tap a seat on the map to add it here.</p>
              )}
            </div>

            <div className="flex items-baseline justify-between gap-3 rounded-lg bg-paper-2 px-3.5 py-3">
              <b
                className={cn("font-mono text-[30px] leading-none font-semibold tabular-nums", p.holding ? "text-red-dark" : "text-ink-3")}
                aria-label={p.holding ? `${p.clock} left on your hold` : undefined}
              >
                {p.clock}
              </b>
              <span className="text-right text-xs tracking-[.08em] text-ink-2 uppercase">{hint}</span>
            </div>

            {warn && <p className="text-sm font-medium text-red-dark">{p.notice}</p>}

            {n > 0 && (
              <div className="grid gap-1.5 text-sm text-ink-2">
                {p.lines.map((l) => (
                  <div key={l.label} className="flex justify-between">
                    <span>{l.label}</span>
                    <span className="tabular-nums">{rupees(l.paise)}</span>
                  </div>
                ))}
                <div className="flex justify-between">
                  <span>Convenience fee</span>
                  <span className="tabular-nums">{rupees(p.fee)}</span>
                </div>
                <div className="mt-0.5 flex items-baseline justify-between border-t border-ink/20 pt-2 text-[17px] font-semibold text-ink">
                  <span>Total</span>
                  <b className="font-cond text-[30px] leading-none font-extrabold tabular-nums">{rupees(p.total)}</b>
                </div>
              </div>
            )}
          </div>

          <div className="mt-auto grid gap-2 px-6 pb-6">
            <Button disabled={!n || p.proceeding} onClick={p.onProceed} className="w-full" aria-describedby="pay-note">
              {cta}
            </Button>
            <p id="pay-note" className="text-center text-xs text-ink-3">
              {p.busy ? "Holding your seats…" : "Test-mode payments · no real money moves"}
            </p>
          </div>
        </div>
      </aside>

      {/* phone bottom sheet */}
      <div
        role="region"
        aria-label="Your booking"
        className="sm-sheet fixed inset-x-0 bottom-0 z-20 rounded-t-[18px] bg-paper px-4 pt-3.5 pb-[max(18px,env(safe-area-inset-bottom))] text-ink shadow-[0_-12px_40px_rgba(0,0,0,.4)] lg:hidden"
      >
        <div aria-hidden="true" className="mx-auto mb-3 h-1 w-10 rounded-full bg-ink/20" />
        <div className="flex min-h-[38px] items-center justify-between gap-3">
          {n ? (
            <Picks picks={p.picks} onRemove={p.onRemove} scroll />
          ) : (
            <p className="text-sm text-ink-2">Tap seats to pick · up to 10</p>
          )}
          <b
            className={cn("shrink-0 font-mono text-[22px] font-semibold tabular-nums", p.holding ? "text-red-dark" : "text-ink-3")}
            title={hint}
          >
            {p.clock}
          </b>
        </div>
        {warn && <p className="mt-1.5 text-[13px] font-medium text-red-dark">{p.notice}</p>}
        <div className="mt-3 flex items-center justify-between gap-3">
          <div>
            <div className="text-xs text-ink-2">
              {n ? `${n} ${n === 1 ? "seat" : "seats"} · incl. ${rupees(p.fee)} fee` : HOLD_COPY}
            </div>
            <b className="font-cond text-[30px] leading-none font-extrabold tabular-nums">{rupees(p.total)}</b>
          </div>
          <Button disabled={!n || p.proceeding} onClick={p.onProceed}>
            {p.proceeding ? "…" : "Pay"}
          </Button>
        </div>
      </div>
    </>
  );
}

function Picks({ picks, onRemove, scroll }: { picks: Props["picks"]; onRemove: (id: string) => void; scroll?: boolean }) {
  return (
    <ul className={cn("flex list-none gap-1.5 p-0", scroll ? "min-w-0 overflow-x-auto [scrollbar-width:none]" : "flex-wrap")}>
      {picks.map((s) => (
        <li key={s.id} className="shrink-0">
          <button
            type="button"
            onClick={() => onRemove(s.id)}
            aria-label={`Remove ${s.name}`}
            className="group inline-flex cursor-pointer items-center gap-1 rounded-chip bg-ink py-1.5 pr-2 pl-2.5 font-cond text-[17px] font-bold tracking-[.04em] text-paper"
          >
            {s.name}
            <X aria-hidden="true" className="size-3.5 opacity-50 group-hover:opacity-100" />
          </button>
        </li>
      ))}
    </ul>
  );
}
