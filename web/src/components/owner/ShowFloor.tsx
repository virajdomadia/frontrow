"use client";

import { X } from "lucide-react";
import QRCode from "qrcode";
import { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
import { changedSeats, indexLayout, statusOf, tierPalette, type SeatState } from "@/components/seat-map/core";
import { SeatMap, type SeatLook } from "@/components/seat-map/SeatMap";
import { useSeatState } from "@/components/seat-map/useSeatState";
import { Button } from "@/components/ui/button";
import { ApiRequestError } from "@/lib/api-error";
import { messageOf, send } from "@/lib/client";
import { rupees, showTime } from "@/lib/format";
import type { Layout, OwnerShow, SeatSnapshot, TicketBundle } from "@/lib/types";
import { cn } from "@/lib/utils";

const REASONS = [
  { key: "broken", label: "Broken" },
  { key: "staff", label: "Staff" },
  { key: "guests", label: "Guests" },
] as const;

type Loaded = { layout: Layout; seats: SeatSnapshot };
type Mode = "sell" | "block";
const MAX_SALE = 10;

/** One show's live map on the Today board: loads its layout and seats, then the live part. */
export function ShowFloor({
  show,
  demo,
  onChange,
  onCancelled,
}: {
  show: OwnerShow;
  demo: boolean;
  onChange: () => void;
  onCancelled: (summary: string) => void;
}) {
  const [cancelling, setCancelling] = useState(false);
  const [loaded, setLoaded] = useState<Loaded | null>(null);
  const [error, setError] = useState("");
  const titleId = useId();
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
    <section aria-labelledby={titleId} className="rounded-card border border-border bg-paper p-4 sm:p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <h2 id={titleId} className="font-cond text-2xl font-bold uppercase">
          {show.film.title} <span className="font-normal text-muted-foreground normal-case">· {showTime(show.starts_at)} · {show.screen_name}</span>
        </h2>
        {new Date(show.starts_at).getTime() > Date.now() && (
          <Button variant="paper" size="sm" disabled={demo} onClick={() => setCancelling(true)}>
            Cancel show
          </Button>
        )}
      </div>
      <CancelDialog open={cancelling} show={show} onClose={() => setCancelling(false)} onDone={onCancelled} />
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
  const [mode, setMode] = useState<Mode>("sell");
  const [picked, setPicked] = useState<string[]>([]);
  const [receipt, setReceipt] = useState<TicketBundle | null>(null);
  // The sale in flight or unanswered: its seats and key. A retry with the same seats sends the
  // same key, so a sale that went through but whose answer was lost comes back as its receipt.
  const sale = useRef<{ key: string; seats: string } | null>(null);
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
    setPicked((p) => {
      const kept = p.filter((id) => !state.sold.has(id) || state.blocked.has(id) || sale.current?.seats.includes(id));
      return kept.length === p.length ? p : kept;
    });
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
      if (mode === "sell" && state.blocked.has(id)) return setNote(`${name(id)} is blocked. Put it back on sale first.`);
      if (!state.blocked.has(id) && st !== "free" && st !== "mine")
        return setNote(`${name(id)} is ${st === "sold" ? "sold" : "held by a customer"}.`);
      if (mode === "sell" && !picked.includes(id) && picked.length >= MAX_SALE) return setNote(`Up to ${MAX_SALE} seats per sale.`);
      setPicked((p) => (p.includes(id) ? p.filter((x) => x !== id) : [...p, id]));
    },
    [mode, name, open, picked, state],
  );

  const toBlock = picked.filter((id) => !state.blocked.has(id));
  const toFree = picked.filter((id) => state.blocked.has(id));
  const total = picked.reduce((a, id) => a + (show.prices?.[index.byId.get(id)?.tier ?? ""] ?? 0), 0);
  async function sell() {
    const seats = [...picked].sort().join();
    if (sale.current?.seats !== seats) sale.current = { key: crypto.randomUUID().replaceAll("-", ""), seats };
    setBusy(true);
    try {
      const bundle = await send<TicketBundle>("POST", `/owner/shows/${show.id}/counter-orders`, {
        seat_ids: picked,
        idempotency_key: sale.current.key,
      });
      sale.current = null;
      setReceipt(bundle);
      setNote(`${bundle.tickets.map((t) => t.label).join(", ")} sold at the counter.`);
      setPicked([]);
      onChange();
    } catch (e) {
      // A definite "no" (taken, held, closed) ends this sale; anything else may have gone
      // through, so the seats and key stay for a retry.
      if (e instanceof ApiRequestError && e.status >= 400 && e.status < 500) sale.current = null;
      setNote(messageOf(e, "No answer from the till. Tap Sell again: the same sale can't be charged twice."));
    } finally {
      setBusy(false);
    }
  }

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
        <div role="radiogroup" aria-label="What a tap does" className="flex w-fit rounded-btn border border-ink/25 p-0.5">
          {(["sell", "block"] as const).map((m) => (
            <button
              key={m}
              type="button"
              role="radio"
              aria-checked={mode === m}
              onClick={() => {
                setMode(m);
                setPicked([]);
              }}
              className={cn("cursor-pointer rounded-[5px] px-3 py-1.5 text-sm font-semibold", mode === m ? "bg-ink text-paper" : "text-ink-2 hover:text-ink")}
            >
              {m === "sell" ? "Sell at the counter" : "Block seats"}
            </button>
          ))}
        </div>
      )}
      {open && mode === "sell" && (
        <div className="flex flex-wrap items-center gap-3">
          <Button disabled={demo || busy || !picked.length} onClick={() => void sell()}>
            {picked.length ? `Sell ${picked.length} · collect ${rupees(total)} cash` : "Pick seats to sell"}
          </Button>
          {picked.length > 0 && <span className="text-sm text-ink-2">{picked.map(name).join(", ")}</span>}
        </div>
      )}
      {open && mode === "block" && (
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
      {demo && <p className="text-sm text-ink-2">The demo owner can look but not sell or block: this is a real, public cinema.</p>}
      <p aria-live="polite" className="min-h-5 text-sm text-ink">
        {note}
      </p>
      <Receipt bundle={receipt} onClose={() => setReceipt(null)} />
    </div>
  );
}

/** The counter sale's tickets: one QR per seat for the customer to photograph or scan. */
function Receipt({ bundle, onClose }: { bundle: TicketBundle | null; onClose: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  const [svgs, setSvgs] = useState<string[]>([]);
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (bundle && !d.open) d.showModal();
    if (!bundle && d.open) d.close();
    if (!bundle) return setSvgs([]);
    let live = true;
    Promise.all(bundle.tickets.map((t) => QRCode.toString(t.qr_token, { type: "svg", margin: 1, errorCorrectionLevel: "M" }))).then(
      (out) => live && setSvgs(out),
    );
    return () => {
      live = false;
    };
  }, [bundle]);

  return (
    <dialog
      ref={ref}
      onClose={onClose}
      aria-labelledby={titleId}
      className="m-auto max-h-[calc(100dvh-32px)] w-[min(560px,100%-32px)] overflow-y-auto rounded-card bg-paper p-6 text-ink shadow-[0_30px_80px_rgb(42_11_30_/_.35)] backdrop:bg-ink/60"
    >
      {bundle && (
        <>
          <div className="mb-4 flex items-start justify-between gap-4">
            <div>
              <h2 id={titleId} className="font-cond text-3xl font-extrabold uppercase">
                Sold · {rupees(bundle.order.total_paise)} cash
              </h2>
              <p className="mt-1 text-sm text-ink-2">
                {bundle.order.show.film.title} · {showTime(bundle.order.show.starts_at)}. Each QR is a ticket: the door scans it like
                any other.
              </p>
            </div>
            <button type="button" onClick={onClose} aria-label="Close" className="-mt-1 -mr-2 cursor-pointer rounded-btn p-2 text-ink-2 hover:bg-ink/10 hover:text-ink">
              <X className="size-5" aria-hidden="true" />
            </button>
          </div>
          <ul className="grid list-none grid-cols-2 gap-3 p-0 sm:grid-cols-3">
            {bundle.tickets.map((t, i) => (
              <li key={t.id} className="grid justify-items-center gap-1 rounded-card border border-border bg-white p-2">
                <div
                  role="img"
                  aria-label={`Ticket QR for seat ${t.label}`}
                  className="size-32 [&_svg]:size-full"
                  // The SVG comes from the qrcode library, built from our own signed token.
                  dangerouslySetInnerHTML={{ __html: svgs[i] ?? "" }}
                />
                <b className="font-cond text-xl">{t.label}</b>
                <span className="text-xs text-ink-2">{t.tier_label}</span>
              </li>
            ))}
          </ul>
          <Button className="mt-5 w-full" onClick={onClose}>
            Done
          </Button>
        </>
      )}
    </dialog>
  );
}

type CancelResult = { refunded: number; refunded_paise: number; refund_pending: number; remaining: number; emails?: Record<string, number> };

const EMAIL_WORDS: Record<string, string> = {
  sent: "sent",
  queued: "still to send",
  failed: "failed",
  not_sent: "not sent (email is off on this site)",
  logged: "written to the server log",
  skipped: "skipped (demo accounts)",
};

/** L5 · Cancel a show: a reason for the buyers, then refund everyone and email them. The API
 *  works in batches and is safe to repeat, so the dialog calls it until nothing is left. */
function CancelDialog({ open, show, onClose, onDone }: { open: boolean; show: OwnerShow; onClose: () => void; onDone: (summary: string) => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) d.showModal();
    if (!open && d.open) d.close();
  }, [open]);

  async function cancel(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      let r: CancelResult | null = null;
      for (let i = 0; i < 40; i++) {
        r = await send<CancelResult>("POST", `/owner/shows/${show.id}/cancel`, { reason: reason.trim() });
        if (!r.remaining && !r.emails?.queued) break;
      }
      if (!r) return;
      const mail = Object.entries(r.emails ?? {})
        .map(([k, n]) => `${n} ${EMAIL_WORDS[k] ?? k}`)
        .join(", ");
      onDone(
        `${show.film.title} at ${showTime(show.starts_at)} is cancelled. ${r.refunded} ${r.refunded === 1 ? "order" : "orders"} refunded (${rupees(
          r.refunded_paise,
        )})${r.refund_pending ? `, ${r.refund_pending} still waiting on the bank` : ""}. Buyer emails: ${mail || "none"}. Counter buyers get cash back at the box office.`,
      );
      onClose();
    } catch (err) {
      setError(messageOf(err, "The show couldn't be cancelled. Nothing was refunded twice: try again."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <dialog
      ref={ref}
      onClose={onClose}
      aria-labelledby={titleId}
      className="m-auto max-h-[calc(100dvh-32px)] w-[min(520px,100%-32px)] overflow-y-auto rounded-card bg-paper p-6 text-ink shadow-[0_30px_80px_rgb(42_11_30_/_.35)] backdrop:bg-ink/60"
    >
      <form onSubmit={(e) => void cancel(e)} className="grid gap-4">
        <div className="flex items-start justify-between gap-4">
          <h2 id={titleId} className="font-cond text-3xl font-extrabold uppercase">
            Cancel this show?
          </h2>
          <button type="button" onClick={onClose} aria-label="Close" className="-mt-1 -mr-2 cursor-pointer rounded-btn p-2 text-ink-2 hover:bg-ink/10 hover:text-ink">
            <X className="size-5" aria-hidden="true" />
          </button>
        </div>
        <p className="text-sm text-ink-2">
          {show.film.title} · {showTime(show.starts_at)} · {show.screen_name}. {show.sold} {show.sold === 1 ? "ticket" : "tickets"} sold: every
          online buyer is refunded in full and emailed; counter buyers get cash back at the box office. This can&apos;t be undone.
        </p>
        <label className="grid gap-1.5 text-sm font-semibold">
          Reason (buyers see it)
          <textarea
            required
            minLength={3}
            maxLength={300}
            rows={3}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            className="rounded-btn border border-input bg-white px-3 py-2 text-[15px] font-normal text-ink"
          />
        </label>
        {error && (
          <p role="alert" className="text-sm text-red-dark">
            {error}
          </p>
        )}
        <div className="flex flex-wrap justify-end gap-3">
          <Button type="button" variant="paper" onClick={onClose}>
            Keep the show
          </Button>
          <Button type="submit" disabled={busy || reason.trim().length < 3}>
            {busy ? "Refunding…" : "Cancel and refund everyone"}
          </Button>
        </div>
      </form>
    </dialog>
  );
}
