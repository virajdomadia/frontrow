"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { changedSeats, indexLayout, statusOf, tierPalette, type SeatState } from "@/components/seat-map/core";
import { SeatMap, type SeatLook } from "@/components/seat-map/SeatMap";
import { useSeatState } from "@/components/seat-map/useSeatState";
import { Button } from "@/components/ui/button";
import { messageOf, send } from "@/lib/client";
import { showTime } from "@/lib/format";
import type { Layout, OwnerShow, SeatSnapshot } from "@/lib/types";

const REASONS = [
  { key: "broken", label: "Broken" },
  { key: "staff", label: "Staff" },
  { key: "guests", label: "Guests" },
] as const;

type Loaded = { layout: Layout; seats: SeatSnapshot };

/** One show's live map on the Today board: loads its layout and seats, then the live part. */
export function ShowFloor({ show, demo, onChange }: { show: OwnerShow; demo: boolean; onChange: () => void }) {
  const [loaded, setLoaded] = useState<Loaded | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let live = true;
    Promise.all([send<Layout>("GET", `/screens/${show.screen_id}/layout`), send<SeatSnapshot>("GET", `/owner/shows/${show.id}/seats`)]).then(
      ([layout, seats]) => live && setLoaded({ layout, seats }),
      (e) => live && setError(messageOf(e, "Couldn't load this show's seats.")),
    );
    return () => {
      live = false;
    };
  }, [show.id, show.screen_id]);

  return (
    <section aria-labelledby="floor-title" className="rounded-card border border-border bg-paper p-4 sm:p-5">
      <h2 id="floor-title" className="font-cond text-2xl font-bold uppercase">
        {show.film.title} <span className="font-normal text-muted-foreground normal-case">· {showTime(show.starts_at)} · {show.screen_name}</span>
      </h2>
      {error ? (
        <p role="alert" className="mt-3 text-sm text-red-dark">
          {error}
        </p>
      ) : loaded ? (
        <Floor show={show} demo={demo} onChange={onChange} {...loaded} />
      ) : (
        <div aria-hidden="true" className="mt-3 h-[420px] rounded-card bg-paper-2" />
      )}
    </section>
  );
}

function Floor({ show, demo, onChange, layout, seats }: { show: OwnerShow; demo: boolean; onChange: () => void } & Loaded) {
  const index = useMemo(() => indexLayout(layout), [layout]);
  const palette = useMemo(() => tierPalette(layout.tiers, Object.fromEntries(layout.tiers.map((t, i) => [t.key, i]))), [layout.tiers]);
  const tierText = useMemo(() => Object.fromEntries(layout.tiers.map((t) => [t.key, t.label])), [layout.tiers]);
  const { state, polling, stale } = useSeatState(`/owner/shows/${show.id}`, seats);
  const [picked, setPicked] = useState<string[]>([]);
  const [reason, setReason] = useState<(typeof REASONS)[number]["key"]>("broken");
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");
  const [ripple, setRipple] = useState<{ ids: string[] } | null>(null);
  const open = new Date(show.starts_at).getTime() > Date.now();
  const name = useCallback((id: string) => index.byId.get(id)?.label ?? "A seat", [index]);

  // A sale or hold anywhere: ripple it, say it once, and refresh the board's totals.
  const seen = useRef<SeatState>(state);
  useEffect(() => {
    const before = seen.current;
    seen.current = state;
    if (before === state) return;
    const ids = changedSeats(before, state);
    if (!ids.length) return;
    setRipple({ ids });
    setPicked((p) => p.filter((id) => !state.sold.has(id) || state.blocked.has(id)));
    const sold = ids.filter((id) => state.sold.has(id) && !state.blocked.has(id));
    if (sold.length) {
      setNote(`${sold.map(name).join(", ")} just sold.`);
      onChange();
    }
  }, [state, name, onChange]);

  const lookOf = useCallback(
    (id: string): SeatLook => {
      if (picked.includes(id)) return "mine";
      if (state.blocked.has(id)) return "off";
      return statusOf(state, id) === "mine" ? "free" : statusOf(state, id);
    },
    [picked, state],
  );

  const toggle = useCallback(
    (id: string) => {
      if (!open) return setNote("This show has started.");
      const st = statusOf(state, id);
      if (!state.blocked.has(id) && st !== "free" && st !== "mine")
        return setNote(`${name(id)} is ${st === "sold" ? "sold" : "held by a customer"}.`);
      setPicked((p) => (p.includes(id) ? p.filter((x) => x !== id) : [...p, id]));
    },
    [name, open, state],
  );

  const toBlock = picked.filter((id) => !state.blocked.has(id));
  const toFree = picked.filter((id) => state.blocked.has(id));

  async function act(method: "POST" | "DELETE", ids: string[]) {
    setBusy(true);
    try {
      await send(method, `/owner/shows/${show.id}/blocks`, method === "POST" ? { seat_ids: ids, reason } : { seat_ids: ids });
      setNote(`${ids.map(name).join(", ")} ${method === "POST" ? "blocked" : "back on sale"}.`);
      setPicked([]);
      onChange();
    } catch (e) {
      setNote(messageOf(e, "That didn't work. Try again."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mt-3 grid gap-3">
      <p className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-2">
        <span>
          {show.sold} sold · {show.blocked} blocked · {show.seat_count - show.sold - show.blocked} left
        </span>
        <span className={stale ? "text-amber" : "text-ink-3"}>{stale ? "Reconnecting…" : polling ? "Live · refreshes every 5 s" : "Live"}</span>
        <span>Outlined seats are blocked; grey ones are held by customers.</span>
      </p>
      <SeatMap
        index={index}
        lookOf={lookOf}
        onToggle={toggle}
        palette={palette}
        tierText={tierText}
        ripple={ripple}
        label={`${show.film.title} ${showTime(show.starts_at)}: seat map`}
        className="h-[min(440px,60dvh)] rounded-card border border-border bg-plum-2"
      />
      {open && (
        <div className="flex flex-wrap items-center gap-3">
          <label className="flex items-center gap-2 text-sm text-ink-2">
            Reason
            <select
              value={reason}
              onChange={(e) => setReason(e.target.value as typeof reason)}
              className="rounded-btn border border-input bg-paper px-2 py-1.5 text-sm text-ink"
            >
              {REASONS.map((r) => (
                <option key={r.key} value={r.key}>
                  {r.label}
                </option>
              ))}
            </select>
          </label>
          <Button disabled={demo || busy || !toBlock.length} onClick={() => void act("POST", toBlock)}>
            {toBlock.length ? `Block ${toBlock.length} ${toBlock.length === 1 ? "seat" : "seats"}` : "Block seats"}
          </Button>
          <Button variant="paper" disabled={demo || busy || !toFree.length} onClick={() => void act("DELETE", toFree)}>
            {toFree.length ? `Put ${toFree.length} back on sale` : "Put back on sale"}
          </Button>
          {picked.length > 0 && (
            <button type="button" onClick={() => setPicked([])} className="cursor-pointer text-sm text-ink-2 underline underline-offset-4">
              Clear
            </button>
          )}
        </div>
      )}
      {demo && <p className="text-sm text-ink-2">The demo owner can look but not block: this is a real, public cinema.</p>}
      <p aria-live="polite" className="min-h-5 text-sm text-ink">
        {note}
      </p>
    </div>
  );
}
