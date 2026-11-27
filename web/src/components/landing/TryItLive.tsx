"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { changedSeats, indexLayout, statusOf, tierPalette, type SeatState } from "@/components/seat-map/core";
import { SeatMap, type SeatLook } from "@/components/seat-map/SeatMap";
import { useCountdown } from "@/components/seat-map/useCountdown";
import { useSeatState } from "@/components/seat-map/useSeatState";
import { ApiRequestError } from "@/lib/api-error";
import { messageOf, send } from "@/lib/client";
import type { Layout, SeatSnapshot } from "@/lib/types";

type Hall = { layout: Layout; seats: SeatSnapshot; ttl_seconds: number };
type Side = "a" | "b";

const PRICES = { classic: 18000, prime: 26000 };
const TIER_TEXT = { classic: "Classic", prime: "Prime" };

/**
 * L2 · "Try it live": two seat maps of one small hall, side by side. Left is you, right is
 * someone else; both are real holds in a private sandbox (`/demo/hall`, Redis only), and both
 * maps redraw from the same live stream a real seat map uses. Loads when scrolled near, so a
 * visitor who never gets here opens no stream.
 */
export function TryItLive() {
  const box = useRef<HTMLDivElement>(null);
  const [hall, setHall] = useState<Hall | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const io = new IntersectionObserver(
      (entries) => {
        if (!entries.some((e) => e.isIntersecting)) return;
        io.disconnect();
        send<Hall>("GET", "/demo/hall").then(setHall, () => setFailed(true));
      },
      { rootMargin: "300px" },
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);

  return (
    <div ref={box} className="min-h-[420px] sm:min-h-[480px]">
      {hall ? (
        <Halls hall={hall} />
      ) : failed ? (
        <p className="rounded-card border border-border bg-paper px-5 py-4 text-sm text-ink-2">
          The live demo is resting right now.{" "}
          <Link href="/movies" className="font-semibold text-ink underline underline-offset-4">
            Open any film
          </Link>{" "}
          and try the real seat map in two tabs.
        </p>
      ) : (
        <div aria-hidden="true" className="grid h-[420px] gap-4 sm:grid-cols-2">
          <div className="rounded-card bg-paper-2" />
          <div className="rounded-card bg-paper-2" />
        </div>
      )}
    </div>
  );
}

function Halls({ hall }: { hall: Hall }) {
  const index = useMemo(() => indexLayout(hall.layout), [hall.layout]);
  const palette = useMemo(() => tierPalette(hall.layout.tiers, PRICES), [hall.layout.tiers]);
  const { state, snapshot, offset, polling, refresh } = useSeatState("/demo/hall", hall.seats);
  const [note, setNote] = useState("");
  const [ripple, setRipple] = useState<Record<Side, { ids: string[] } | null>>({ a: null, b: null });

  // In the stream's terms `mine` is the left side's and `held` the right side's.
  const ownerOf = useCallback((s: SeatState, id: string): Side | null => {
    const st = statusOf(s, id);
    return st === "mine" ? "a" : st === "held" ? "b" : null;
  }, []);

  const seen = useRef(state);
  useEffect(() => {
    const before = seen.current;
    seen.current = state;
    if (before === state) return;
    const changed = changedSeats(before, state);
    if (!changed.length) return;
    // Each map ripples what the *other* side just did: that's the point of the demo.
    const byA = changed.filter((id) => ownerOf(before, id) === "a" || ownerOf(state, id) === "a");
    const byB = changed.filter((id) => ownerOf(before, id) === "b" || ownerOf(state, id) === "b");
    setRipple({ a: byB.length ? { ids: byB } : null, b: byA.length ? { ids: byA } : null });
    const name = (id: string) => index.byId.get(id)?.label ?? "A seat";
    const took = changed.filter((id) => ownerOf(state, id));
    const freed = changed.filter((id) => !ownerOf(state, id));
    const parts: string[] = [];
    if (took.length) parts.push(`${took.map(name).join(", ")} now held on both maps.`);
    if (freed.length) parts.push(`${freed.map(name).join(", ")} free again on both maps.`);
    setNote(parts.join(" "));
  }, [state, index, ownerOf]);

  const act = useCallback(
    async (side: Side, id: string) => {
      const owner = ownerOf(state, id);
      const mine = index.seats.filter((s) => ownerOf(state, s.id) === side).map((s) => s.id);
      const name = index.byId.get(id)?.label ?? "That seat";
      try {
        if (owner === side) await send("DELETE", "/demo/hall/holds", { as: side, seat_ids: [id] });
        else if (owner) return setNote(`${name} is held on the other map.`);
        else await send("POST", "/demo/hall/holds", { as: side, seat_ids: [...mine, id] });
        if (polling) void refresh();
      } catch (e) {
        if (e instanceof ApiRequestError && e.body.code === "seat_taken") setNote(`${name} was just taken on the other map.`);
        else setNote(messageOf(e, "That didn't work. Try again."));
        void refresh();
      }
    },
    [index, ownerOf, polling, refresh, state],
  );

  const firstHeld = (ids: string[]) => ids.map((id) => state.held.get(id)).filter(Boolean).sort()[0] ?? null;
  const theirs = [...state.held.keys()];

  return (
    <div>
      <div className="grid gap-4 sm:grid-cols-2">
        <Panel
          side="a"
          title="You"
          index={index}
          palette={palette}
          lookOf={(id) => look(ownerOf(state, id), "a")}
          onToggle={(id) => void act("a", id)}
          ripple={ripple.a}
          held={snapshot.mine}
          expiresAt={snapshot.mine_expires_at ?? null}
          offset={offset}
        />
        <Panel
          side="b"
          title="Someone across town"
          index={index}
          palette={palette}
          lookOf={(id) => look(ownerOf(state, id), "b")}
          onToggle={(id) => void act("b", id)}
          ripple={ripple.b}
          held={theirs}
          expiresAt={firstHeld(theirs)}
          offset={offset}
        />
      </div>
      <p className="mt-3 text-xs text-ink-3">
        <span className="mr-3 inline-flex items-center gap-1.5">
          <i className="inline-block h-3 w-3.5 rounded-sm bg-red" />
          Held on this map
        </span>
        <span className="mr-3 inline-flex items-center gap-1.5">
          <i className="inline-block h-3 w-3.5 rounded-sm bg-held" />
          Held on the other
        </span>
        {polling ? "Live · refreshes every 5 s." : "Both maps redraw from the same push a real seat map gets."} Demo holds last{" "}
        {hall.ttl_seconds} seconds (real ones, ten minutes) and touch no real show.
      </p>
      <p className="sr-only" aria-live="polite">
        {note}
      </p>
    </div>
  );
}

function look(owner: Side | null, side: Side): SeatLook {
  return owner === null ? "free" : owner === side ? "mine" : "held";
}

type PanelProps = {
  side: Side;
  title: string;
  index: ReturnType<typeof indexLayout>;
  palette: ReturnType<typeof tierPalette>;
  lookOf: (id: string) => SeatLook;
  onToggle: (id: string) => void;
  ripple: { ids: string[] } | null;
  held: string[];
  expiresAt: string | null;
  offset: number;
};

function Panel({ side, title, index, palette, lookOf, onToggle, ripple, held, expiresAt, offset }: PanelProps) {
  const clock = useCountdown(held.length ? expiresAt : null, offset);
  const names = index.seats.filter((s) => held.includes(s.id)).map((s) => s.label);
  return (
    <section aria-labelledby={`try-${side}`} className="fr-stub p-1.5 sm:p-4">
      <div className="mb-2 flex items-baseline justify-between gap-3 px-1.5 pt-1.5 sm:p-0">
        <h3 id={`try-${side}`} className="font-cond text-xl font-bold uppercase">
          {title}
        </h3>
        <p className="text-sm text-ink-2" aria-live="off">
          {names.length ? (
            <>
              <b className="font-cond text-base text-ink">{names.join(", ")}</b> held ·{" "}
              <span className="font-mono tabular-nums text-red-dark">{clock.text}</span>
            </>
          ) : (
            "Tap a seat"
          )}
        </p>
      </div>
      <SeatMap
        index={index}
        lookOf={lookOf}
        onToggle={onToggle}
        palette={palette}
        tierText={TIER_TEXT}
        ripple={ripple}
        fixed
        className="h-[340px] rounded-card border border-border bg-plum-2 sm:h-[360px]"
      />
    </section>
  );
}
