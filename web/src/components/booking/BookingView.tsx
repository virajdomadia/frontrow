"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { FillBadge } from "@/components/events/badges";
import { indexLayout, statusOf, tierPalette, type PlacedSeat, type SeatIndex } from "@/components/seat-map/core";
import { SeatMap, type SeatLook } from "@/components/seat-map/SeatMap";
import { useCountdown } from "@/components/seat-map/useCountdown";
import { useSeatState } from "@/components/seat-map/useSeatState";
import { ApiRequestError } from "@/lib/api-error";
import { messageOf, send } from "@/lib/client";
import { dayParts, rupees, showTime } from "@/lib/format";
import type { HoldGranted, Layout, Order, SeatSnapshot, ShowtimeDetail } from "@/lib/types";
import { cn } from "@/lib/utils";
import { reconcile, takenNames } from "./holds";
import { Legend } from "./Legend";
import { SeatList } from "./SeatList";
import { SignInDialog } from "./SignInDialog";
import { Stub, type StubLine } from "./Stub";

export const MAX_SEATS = 10; // 06 §C: holds over ten → 422 too_many_seats

/** "C7", or "Sec 3 · C7" in an arena where every wedge has its own row A. */
export function seatName(index: SeatIndex, seat: PlacedSeat) {
  if (index.layout.template !== "arena") return seat.label;
  const section = index.sections.find((s) => s.key === seat.section);
  return `${section?.label.replace("Section", "Sec") ?? seat.section} · ${seat.label}`;
}

type Toast = { text: string; tone: "warn" | "info"; key: number };

/**
 * S4: the live map, its legend and the stub that fills as you pick. Every tap is a hold: the
 * whole selection goes to `POST /holds` (all-or-none, 10 minutes, one shared clock); a 409 drops
 * the taken seat and says so; deselecting releases just that seat. The map polls every 5 s, so
 * someone else's hold greys out here within one poll.
 */
export function BookingView({ showtime, layout, snapshot: initial }: { showtime: ShowtimeDetail; layout: Layout; snapshot: SeatSnapshot }) {
  const router = useRouter();
  const index = useMemo(() => indexLayout(layout), [layout]);
  const { state, snapshot, offset, stale, refresh, markHeld } = useSeatState(showtime.id, initial);

  const [selected, setSelected] = useState<string[]>(() => initial.mine);
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

  const prices = useMemo(() => Object.fromEntries(showtime.tiers.map((t) => [t.tier_key, t.price_paise])), [showtime.tiers]);
  const palette = useMemo(() => tierPalette(layout.tiers, prices), [layout.tiers, prices]);
  const tierText = useMemo(
    () => Object.fromEntries(showtime.tiers.map((t) => [t.tier_key, `${t.label} ${rupees(t.price_paise)}`])),
    [showtime.tiers],
  );
  const chosen = useMemo(() => new Set(selected), [selected]);
  const nameOf = useCallback((id: string) => {
    const seat = index.byId.get(id);
    return seat ? seatName(index, seat) : "A seat";
  }, [index]);

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
    (id: string) => {
      adding.current.add(id);
      setSelected((s) => [...s, id]);
      setNotice(`${nameOf(id)} added`);
      enqueue(async () => {
        const want = selectedRef.current;
        if (!want.includes(id)) return void adding.current.delete(id);
        try {
          const granted = await send<HoldGranted>("POST", `/showtimes/${showtime.id}/holds`, { seat_ids: want });
          setExpiresAt(granted.expires_at);
        } catch (e) {
          if (e instanceof ApiRequestError && e.body.code === "seat_taken") {
            const taken = ((e.body.details as { taken?: string[] } | undefined)?.taken ?? [id]).filter(Boolean);
            setSelected((s) => s.filter((x) => !taken.includes(x)));
            markHeld(taken);
            say(takenNames(taken, nameOf));
          } else {
            setSelected((s) => s.filter((x) => x !== id));
            say(
              e instanceof ApiRequestError && e.body.code === "showtime_closed"
                ? "This show has started — booking is closed"
                : messageOf(e, "Couldn't hold that seat. Try again."),
            );
          }
          void refresh();
        } finally {
          adding.current.delete(id);
        }
      });
    },
    [enqueue, markHeld, nameOf, refresh, say, showtime.id],
  );

  const release = useCallback(
    (id: string) => {
      removing.current.add(id);
      setSelected((s) => s.filter((x) => x !== id));
      setNotice(`${nameOf(id)} removed`);
      enqueue(async () => {
        try {
          await send("DELETE", `/showtimes/${showtime.id}/holds`, { seat_ids: [id] });
        } catch {
          // The hold lapses on its own within 10 minutes; nothing to undo for the customer.
        } finally {
          removing.current.delete(id);
          if (!selectedRef.current.length) setExpiresAt(null);
        }
      });
    },
    [enqueue, nameOf, showtime.id],
  );

  const toggle = useCallback(
    (id: string) => {
      const seat = index.byId.get(id);
      if (!seat || proceeding) return;
      const look = lookOf(id);
      if (look === "mine") release(id);
      else if (look !== "free")
        setNotice(`${nameOf(id)} is ${look === "off" ? "not on sale" : look === "held" ? "held by someone else" : "sold"}`);
      else if (selectedRef.current.length >= MAX_SEATS) say(`Up to ${MAX_SEATS} seats per booking`);
      else hold(id);
    },
    [hold, index, lookOf, nameOf, proceeding, release, say],
  );

  const clock = useCountdown(selected.length ? expiresAt : null, offset, {
    title: `Pick seats · ${showtime.event.title} · Frontrow`,
    onZero: () => {
      if (!selectedRef.current.length) return;
      setSelected([]);
      setExpiresAt(null);
      say("Your 10 minutes are up — the seats went back on sale. Pick again to hold them.");
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
      const order = await send<Order>("POST", "/orders", { showtime_id: showtime.id, seat_ids: seats });
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
  const lines: StubLine[] = showtime.tiers
    .map((t) => {
      const n = picks.filter((p) => p.tier === t.tier_key).length;
      return { label: `${n} × ${t.label}`, paise: n * t.price_paise, n };
    })
    .filter((l) => l.n > 0);
  const fee = picks.length * showtime.fee_paise;
  const total = lines.reduce((a, l) => a + l.paise, 0) + fee;
  const { weekday, date } = dayParts(showtime.starts_at);
  const venueShort = showtime.venue.name.replace("Orbit Cinemas · ", "");
  const onSale = useMemo(() => index.seats.filter((s) => s.tier in prices).length, [index, prices]);
  const soldOut = state.sold.size >= onSale;
  const allTaken = !soldOut && state.sold.size + state.held.size >= onSale && !selected.length;

  const stub = {
    title: showtime.event.title,
    venue: showtime.venue.name,
    date: `${weekday} ${date}`,
    time: showTime(showtime.starts_at),
    picks: picks.map((p) => ({ id: p.id, name: seatName(index, p) })),
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
    <div className="mx-auto w-[min(1440px,100%)] lg:grid lg:h-[calc(100dvh-69px)] lg:grid-cols-[1fr_380px] lg:gap-2">
      <section aria-labelledby="book-title" className="relative flex min-h-0 flex-col px-4 pt-4 pb-[200px] lg:px-10 lg:pb-4">
        <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1">
          <h1 id="book-title" className="font-cond text-[26px] leading-none font-extrabold uppercase lg:text-[30px]">
            <span className="hidden lg:inline">{venueShort} · </span>
            {showtime.event.title}
          </h1>
          <p className="flex items-center gap-3 text-[13px] text-muted-foreground lg:text-sm">
            <span>
              {weekday} {date} · {showTime(showtime.starts_at)} · <span className="lg:hidden">{venueShort}</span>
              <span className="hidden lg:inline">{showtime.venue.name}</span>
            </span>
            {soldOut ? <FillBadge fill="sold_out" /> : showtime.fill === "filling" && <FillBadge fill="filling" />}
          </p>
        </div>

        {(soldOut || allTaken) && (
          <div role="status" className="mt-3 flex flex-wrap items-center justify-between gap-3 rounded-card border border-amber/40 bg-amber/10 px-4 py-3 text-sm">
            <span>
              <b className="font-semibold text-screen">{soldOut ? "Sold out." : "Every free seat is held right now."}</b>{" "}
              <span className="text-muted-foreground">
                {soldOut
                  ? "Every seat for this showtime has been sold."
                  : "Holds last 10 minutes — seats come back the moment one lapses. This page checks every 5 seconds."}
              </span>
            </span>
            <Link href={`/events/${showtime.event.slug}`} className="font-semibold text-amber underline underline-offset-4">
              Other showtimes
            </Link>
          </div>
        )}

        <div className="relative mt-3 flex min-h-0 flex-col lg:flex-1">
          {toast && (
            <div
              key={toast.key}
              role="status"
              className={cn(
                "sm-toast pointer-events-none absolute inset-x-3 top-3 z-10 mx-auto w-fit max-w-[min(520px,100%-24px)] rounded-btn px-4 py-2.5 text-center text-sm font-semibold shadow-[0_10px_30px_rgba(0,0,0,.45)]",
                toast.tone === "warn" ? "bg-amber text-plum" : "bg-screen text-plum",
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
            className="h-[440px] rounded-card border border-border bg-plum lg:h-auto lg:min-h-0 lg:flex-1 lg:border-0"
          />
        </div>
        <div className="flex flex-wrap items-center justify-between gap-x-4">
          <Legend tiers={showtime.tiers} palette={palette} />
          <p className={cn("mt-3 text-xs", stale ? "text-amber" : "text-faint")} aria-live="polite">
            {stale ? "Reconnecting… seat colours may be a few seconds old" : "Live · refreshes every 5 s"}
          </p>
        </div>
        <SeatList index={index} lookOf={lookOf} onToggle={toggle} tierText={tierText} />
      </section>

      <Stub {...stub} />
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
