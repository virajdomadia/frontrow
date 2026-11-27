"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { CertBadge, certNote, FillBadge } from "@/components/movies/badges";
import { changedSeats, indexLayout, statusOf, tierPalette } from "@/components/seat-map/core";
import { SeatMap, type SeatLook } from "@/components/seat-map/SeatMap";
import { useCountdown } from "@/components/seat-map/useCountdown";
import { useSeatState } from "@/components/seat-map/useSeatState";
import { ApiRequestError } from "@/lib/api-error";
import { messageOf, send } from "@/lib/client";
import { dayParts, rupees, showTime } from "@/lib/format";
import type { HoldGranted, Layout, Order, SeatSnapshot, ShowDetail } from "@/lib/types";
import { cn } from "@/lib/utils";
import { pickTogether, reconcile, takenNames } from "./holds";
import { HowMany } from "./HowMany";
import { Legend } from "./Legend";
import { SeatList } from "./SeatList";
import { SignInDialog } from "./SignInDialog";
import { Stub, type StubLine } from "./Stub";

export const MAX_SEATS = 10; // 06 §C: holds over ten → 422 too_many_seats

type Toast = { text: string; tone: "warn" | "info"; key: number };

/**
 * C5 + C6: the certificate notice and "How many seats?", then the live map, its legend and the
 * stub that fills as you pick. A tap picks that many seats together; every pick is a hold — the
 * whole selection goes to `POST /holds` (all-or-none, 10 minutes, one shared clock); a 409 drops
 * the taken seats and says so ("F7 was just taken"); deselecting releases just that seat. The
 * map polls every 5 s, so someone else's hold greys out here within one poll.
 */
export function BookingView({ show, layout, snapshot: initial }: { show: ShowDetail; layout: Layout; snapshot: SeatSnapshot }) {
  const router = useRouter();
  const index = useMemo(() => indexLayout(layout), [layout]);
  const { state, snapshot, offset, stale, polling, refresh, markHeld } = useSeatState(show.id, initial);

  const [selected, setSelected] = useState<string[]>(() => initial.mine);
  // Coming back to a hold you already have skips the question; otherwise ask first (R5).
  const [count, setCount] = useState<number | null>(() => (initial.mine.length ? initial.mine.length : null));
  const [asking, setAsking] = useState(() => !initial.mine.length);
  const [expiresAt, setExpiresAt] = useState<string | null>(initial.mine_expires_at ?? null);
  const [notice, setNotice] = useState("");
  const [toast, setToast] = useState<Toast | null>(null);
  const [proceeding, setProceeding] = useState(false);
  const [askSignIn, setAskSignIn] = useState(false);
  const [pending, setPending] = useState(0);

  const selectedRef = useRef(selected);
  selectedRef.current = selected;
  const adding = useRef(new Set<string>());
  const removing = useRef(new Set<string>());
  const queue = useRef<Promise<void>>(Promise.resolve());

  const prices = useMemo(() => Object.fromEntries(show.tiers.map((t) => [t.tier_key, t.price_paise])), [show.tiers]);
  const palette = useMemo(() => tierPalette(layout.tiers, prices), [layout.tiers, prices]);
  const tierText = useMemo(() => Object.fromEntries(show.tiers.map((t) => [t.tier_key, `${t.label} ${rupees(t.price_paise)}`])), [show.tiers]);
  const chosen = useMemo(() => new Set(selected), [selected]);
  const nameOf = useCallback((id: string) => index.byId.get(id)?.label ?? "A seat", [index]);

  const say = useCallback((text: string, tone: Toast["tone"] = "warn") => {
    setNotice(text);
    setToast({ text, tone, key: Date.now() });
  }, []);

  useEffect(() => {
    if (!toast) return;
    const t = window.setTimeout(() => setToast(null), 5000);
    return () => window.clearTimeout(t);
  }, [toast]);

  // Each poll: the server's `mine` is the truth, except for taps still in flight.
  useEffect(() => {
    const r = reconcile(selectedRef.current, snapshot.mine, adding.current, removing.current);
    if (r.selected.join() !== selectedRef.current.join()) setSelected(r.selected);
    if (r.lost.length) say(`Your hold on ${r.lost.map(nameOf).join(", ")} ended — ${r.lost.length === 1 ? "it's" : "they're"} back on sale`);
    if (snapshot.mine.length && snapshot.mine_expires_at) setExpiresAt(snapshot.mine_expires_at);
    else if (!snapshot.mine.length && !adding.current.size) setExpiresAt(null);
  }, [snapshot, nameOf, say]);

  // Other people's changes: ripple each seat at once; tell screen readers at most every 4 s.
  const [ripple, setRipple] = useState<{ ids: string[] } | null>(null);
  const [liveNote, setLiveNote] = useState("");
  const seen = useRef(state);
  const heard = useRef({ taken: [] as string[], freed: [] as string[], timer: 0 });
  useEffect(() => {
    const before = seen.current;
    seen.current = state;
    if (before === state) return;
    const ids = changedSeats(before, state).filter(
      (id) => statusOf(before, id) !== "mine" && statusOf(state, id) !== "mine" && !selectedRef.current.includes(id),
    );
    if (!ids.length) return;
    setRipple({ ids });
    const h = heard.current;
    for (const id of ids) (statusOf(state, id) === "free" ? h.freed : h.taken).push(id);
    if (h.timer) return;
    h.timer = window.setTimeout(() => {
      const parts: string[] = [];
      if (h.taken.length) parts.push(h.taken.length <= 3 ? `${takenNames(h.taken, nameOf)}.` : `${h.taken.length} seats were just taken.`);
      if (h.freed.length) parts.push(h.freed.length === 1 ? `${nameOf(h.freed[0])} is free again.` : `${h.freed.length} seats are free again.`);
      // Cleared first, so the same sentence twice ("D4 is free again.") is still read out.
      setLiveNote("");
      window.setTimeout(() => setLiveNote(parts.join(" ")), 50);
      heard.current = { taken: [], freed: [], timer: 0 };
    }, 4000);
  }, [state, nameOf]);
  useEffect(() => () => window.clearTimeout(heard.current.timer), []);

  const lookOf = useCallback(
    (id: string): SeatLook => {
      const seat = index.byId.get(id);
      if (!seat || !(seat.tier in prices)) return "off";
      if (state.sold.has(id)) return "sold";
      if (chosen.has(id)) return "mine";
      const status = statusOf(state, id);
      return status === "mine" ? "free" : status; // ours from a lapsed request: free to re-take
    },
    [index, prices, state, chosen],
  );

  const enqueue = useCallback((job: () => Promise<void>) => {
    setPending((n) => n + 1);
    queue.current = queue.current.then(job).finally(() => setPending((n) => n - 1));
  }, []);

  const hold = useCallback(
    (ids: string[]) => {
      for (const id of ids) adding.current.add(id);
      setSelected((s) => [...s, ...ids.filter((id) => !s.includes(id))]);
      setNotice(`${ids.map(nameOf).join(", ")} added`);
      enqueue(async () => {
        const want = selectedRef.current;
        if (!ids.some((id) => want.includes(id))) return void ids.forEach((id) => adding.current.delete(id));
        try {
          const granted = await send<HoldGranted>("POST", `/shows/${show.id}/holds`, { seat_ids: want });
          setExpiresAt(granted.expires_at);
        } catch (e) {
          if (e instanceof ApiRequestError && e.body.code === "seat_taken") {
            const taken = ((e.body.details as { taken?: string[] } | undefined)?.taken ?? ids).filter(Boolean);
            setSelected((s) => s.filter((x) => !taken.includes(x)));
            markHeld(taken);
            say(`${takenNames(taken, nameOf)} — the rest of your seats are still yours`);
          } else {
            setSelected((s) => s.filter((x) => !ids.includes(x)));
            say(
              e instanceof ApiRequestError && e.body.code === "show_closed"
                ? "This show has started — booking is closed"
                : messageOf(e, "Couldn't hold that seat. Try again."),
            );
          }
          void refresh();
        } finally {
          for (const id of ids) adding.current.delete(id);
        }
      });
    },
    [enqueue, markHeld, nameOf, refresh, say, show.id],
  );

  const release = useCallback(
    (ids: string[]) => {
      for (const id of ids) removing.current.add(id);
      setSelected((s) => s.filter((x) => !ids.includes(x)));
      setNotice(`${ids.map(nameOf).join(", ")} removed`);
      enqueue(async () => {
        try {
          await send("DELETE", `/shows/${show.id}/holds`, { seat_ids: ids });
        } catch {
          // The hold lapses on its own within 10 minutes; nothing to undo for the customer.
        } finally {
          for (const id of ids) removing.current.delete(id);
          if (!selectedRef.current.length) setExpiresAt(null);
        }
      });
    },
    [enqueue, nameOf, show.id],
  );

  const toggle = useCallback(
    (id: string) => {
      const seat = index.byId.get(id);
      if (!seat || proceeding) return;
      const look = lookOf(id);
      if (look === "mine") return release([id]);
      if (look !== "free")
        return setNotice(`${nameOf(id)} is ${look === "off" ? "not on sale" : look === "held" ? "held by someone else" : "sold"}`);
      const want = count ?? 1;
      const current = selectedRef.current;
      if (current.length >= want) {
        // A full selection and a tap elsewhere: move the whole group there (BookMyShow's way).
        const group = pickTogether(index.rows[seat.rowIndex].seats, id, want, (s) => lookOf(s) === "free");
        if (current.length) release(current);
        return hold(group);
      }
      if (current.length >= MAX_SEATS) return say(`Up to ${MAX_SEATS} seats per booking`);
      hold(pickTogether(index.rows[seat.rowIndex].seats, id, want - current.length, (s) => lookOf(s) === "free"));
    },
    [count, hold, index, lookOf, nameOf, proceeding, release, say],
  );

  const clock = useCountdown(selected.length ? expiresAt : null, offset, {
    title: `Pick seats · ${show.film.title} · Frontrow`,
    onZero: () => {
      if (!selectedRef.current.length) return;
      setSelected([]);
      setExpiresAt(null);
      say("Your seats were released — 10 minutes are up. Pick again to hold them.");
      void refresh();
    },
  });

  async function proceed() {
    if (!selectedRef.current.length || proceeding) return;
    setProceeding(true);
    await queue.current;
    const seats = selectedRef.current;
    if (!seats.length) return setProceeding(false);
    try {
      const order = await send<Order>("POST", "/orders", { show_id: show.id, seat_ids: seats });
      router.push(`/checkout/${order.id}`);
    } catch (e) {
      setProceeding(false);
      if (e instanceof ApiRequestError && e.status === 401) return setAskSignIn(true);
      say(messageOf(e, "Couldn't start checkout. Try again."));
      void refresh();
    }
  }

  // Picks in hall order (front to back, left to right), not tap order.
  const picks = index.seats.filter((s) => chosen.has(s.id));
  const lines: StubLine[] = show.tiers
    .map((t) => {
      const n = picks.filter((p) => p.tier === t.tier_key).length;
      return { label: `${n} × ${t.label}`, paise: n * t.price_paise, n };
    })
    .filter((l) => l.n > 0);
  const fee = picks.length * show.fee_paise;
  const total = lines.reduce((a, l) => a + l.paise, 0) + fee;
  const { weekday, date } = dayParts(show.starts_at);
  const onSale = useMemo(() => index.seats.filter((s) => s.tier in prices).length, [index, prices]);
  const soldOut = state.sold.size >= onSale;
  const allTaken = !soldOut && state.sold.size + state.held.size >= onSale && !selected.length;
  const short = count !== null && selected.length > 0 && selected.length < count;

  const stub = {
    title: show.film.title,
    venue: `${show.cinema.name} · ${show.screen.name}`,
    date: `${weekday} ${date}`,
    time: showTime(show.starts_at),
    picks: picks.map((p) => ({ id: p.id, name: p.label })),
    lines,
    fee,
    total,
    notice,
    onRemove: toggle,
    clock: clock.text,
    holding: clock.active,
    busy: pending > 0,
    proceeding,
    onProceed: proceed,
  };

  return (
    <div className="mx-auto w-[min(1440px,100%)] lg:grid lg:h-[calc(100dvh-74px)] lg:grid-cols-[1fr_380px] lg:gap-2">
      <section aria-labelledby="book-title" className="relative flex min-h-0 flex-col px-4 pt-4 pb-[200px] lg:px-10 lg:pb-4">
        <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1">
          <h1 id="book-title" className="flex items-center gap-2.5 font-cond text-[26px] leading-none font-extrabold uppercase lg:text-[30px]">
            {show.film.title}
            <CertBadge cert={show.film.cert} />
          </h1>
          <p className="flex flex-wrap items-center gap-3 text-[13px] text-muted-foreground lg:text-sm">
            <span>
              {weekday} {date} · {showTime(show.starts_at)} · {show.language} {show.format} · {show.cinema.name} · {show.screen.name}
            </span>
            {soldOut ? <FillBadge fill="sold_out" /> : show.fill === "filling" && <FillBadge fill="filling" />}
            {count !== null && (
              <button
                type="button"
                onClick={() => setAsking(true)}
                className="cursor-pointer rounded-chip border border-ink/25 px-2 py-0.5 text-xs font-semibold text-ink hover:border-ink"
              >
                {count} {count === 1 ? "seat" : "seats"} · change
              </button>
            )}
          </p>
        </div>

        {(soldOut || allTaken) && (
          <div role="status" className="mt-3 flex flex-wrap items-center justify-between gap-3 rounded-card border border-amber/40 bg-amber/10 px-4 py-3 text-sm">
            <span>
              <b className="font-semibold text-ink">{soldOut ? "Sold out." : "Every free seat is held right now."}</b>{" "}
              <span className="text-muted-foreground">
                {soldOut
                  ? "Every seat for this show has been sold."
                  : "Holds last 10 minutes, and seats come back here the moment one lapses."}
              </span>
            </span>
            <Link href={`/movies/${show.film.slug}/shows`} className="font-semibold text-amber underline underline-offset-4">
              Other showtimes
            </Link>
          </div>
        )}
        {short && (
          <p role="status" className="mt-3 rounded-card bg-paper-2 px-4 py-2.5 text-sm text-ink-2">
            Not enough free seats together there — tap {count! - selected.length} more {count! - selected.length === 1 ? "seat" : "seats"} to make {count}.
          </p>
        )}

        {/* Above the map: on a phone the booking sheet covers whatever sits under it. */}
        <Legend tiers={show.tiers} palette={palette} />
        <div className="relative mt-3 flex min-h-0 flex-col lg:flex-1">
          {toast && (
            <div
              key={toast.key}
              role="status"
              className={cn(
                "sm-toast pointer-events-none absolute inset-x-3 top-3 z-10 mx-auto w-fit max-w-[min(520px,100%-24px)] rounded-btn px-4 py-2.5 text-center text-sm font-semibold shadow-[0_10px_30px_rgb(42_11_30_/_.3)]",
                toast.tone === "warn" ? "bg-ink text-paper" : "bg-paper text-ink",
              )}
            >
              {toast.text}
            </div>
          )}
          <SeatMap
            index={index}
            lookOf={lookOf}
            onToggle={toggle}
            palette={palette}
            tierText={tierText}
            ripple={ripple}
            className="h-[min(520px,62dvh)] rounded-card border border-border bg-plum-2 lg:h-auto lg:min-h-0 lg:flex-1"
          />
        </div>
        <div className="flex flex-wrap items-center justify-between gap-x-4">
          <p className={cn("mt-3 text-xs", stale ? "text-amber" : "text-ink-3")} aria-live="polite">
            {stale ? "Reconnecting… seat colours may be a few seconds old" : polling ? "Live · refreshes every 5 s" : "Live: seats change here as others pick them"}
          </p>
          <p className="sr-only" aria-live="polite">
            {liveNote}
          </p>
        </div>
        <SeatList index={index} lookOf={lookOf} onToggle={toggle} tierText={tierText} />
      </section>

      <Stub {...stub} />
      <HowMany
        open={asking}
        cert={show.film.cert}
        certNote={certNote(show.film.cert)}
        title={show.film.title}
        initial={count ?? 2}
        max={MAX_SEATS}
        onPick={(n) => {
          setCount(n);
          setAsking(false);
          // Fewer seats than already held: let go of the extra ones (furthest from the screen first).
          const current = selectedRef.current;
          if (current.length > n) release(current.slice(n));
        }}
        onClose={() => {
          setAsking(false);
          if (count === null) setCount(2);
        }}
      />
      <SignInDialog
        open={askSignIn}
        onClose={() => setAskSignIn(false)}
        onDone={() => {
          setAskSignIn(false);
          router.refresh();
          void proceed();
        }}
      />
    </div>
  );
}
