"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { useCountdown } from "@/components/seat-map/useCountdown";
import { Button, buttonVariants } from "@/components/ui/button";
import { ApiRequestError } from "@/lib/api-error";
import { messageOf, send } from "@/lib/client";
import { dayParts, rupees, showTime } from "@/lib/format";
import type { Order } from "@/lib/types";
import { cn } from "@/lib/utils";

type Phase = "idle" | "paying" | "confirming" | "torn";

type RazorpayResponse = { razorpay_payment_id: string; razorpay_order_id: string; razorpay_signature: string };
type RazorpayInstance = { open: () => void; on: (event: string, cb: (r: { error?: { description?: string } }) => void) => void };
declare global {
  interface Window {
    Razorpay?: new (options: Record<string, unknown>) => RazorpayInstance;
  }
}

const RAZORPAY_JS = "https://checkout.razorpay.com/v1/checkout.js";
const CONFIRM_POLL_MS = 2000;
const SLOW_AFTER_MS = 20_000;

function loadRazorpay(): Promise<void> {
  if (window.Razorpay) return Promise.resolve();
  return new Promise((resolve, reject) => {
    const s = document.createElement("script");
    s.src = RAZORPAY_JS;
    s.async = true;
    s.onload = () => resolve();
    s.onerror = () => reject(new Error("Razorpay didn't load"));
    document.head.appendChild(s);
  });
}

/**
 * S5 checkout + S8 outcomes. Pay opens Razorpay Checkout (test mode) — or, with no Razorpay keys
 * configured, a clearly-labelled test payment — then the `verify` fast path confirms; if the
 * answer isn't "paid" yet the page polls the order ("Confirming…", and after 20 s "Payment
 * received, confirming…") until the webhook lands. Paid → the stub tears off into the ticket.
 */
export function Checkout({ initial }: { initial: Order }) {
  const router = useRouter();
  const [order, setOrder] = useState(initial);
  const [phase, setPhase] = useState<Phase>("idle");
  const [error, setError] = useState("");
  const [slow, setSlow] = useState(false);
  const [offset] = useState(0);
  const confirmingSince = useRef<number | null>(null);

  const holdClock = useCountdown(order.status === "pending" ? order.hold_expires_at : null, offset, {
    title: `Checkout · ${order.showtime.event.title} · Frontrow`,
  });
  const payClock = useCountdown(order.status === "pending" ? order.pay_by : null, offset, {
    onZero: () => void reload(),
  });

  const reload = useCallback(async () => {
    try {
      const next = await send<Order>("GET", `/orders/${order.id}`);
      setOrder(next);
      return next;
    } catch {
      return null;
    }
  }, [order.id]);

  const done = useCallback(
    (paid: Order) => {
      setOrder(paid);
      const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      setPhase("torn");
      window.setTimeout(() => router.push(`/tickets/${paid.id}`), reduce ? 300 : 1100);
    },
    [router],
  );

  // "Confirming…": poll until the webhook (or verify) has turned the order into tickets.
  useEffect(() => {
    if (phase !== "confirming") return;
    confirmingSince.current ??= Date.now();
    const t = window.setInterval(async () => {
      const next = await reload();
      if (next?.status === "paid") done(next);
      else if (next && next.status !== "pending") setPhase("idle");
      if (Date.now() - (confirmingSince.current ?? Date.now()) > SLOW_AFTER_MS) setSlow(true);
    }, CONFIRM_POLL_MS);
    return () => window.clearInterval(t);
  }, [phase, reload, done]);

  function settle(next: Order) {
    if (next.status === "paid") return done(next);
    setOrder(next);
    setPhase(next.status === "pending" ? "confirming" : "idle");
  }

  async function payDemo() {
    setPhase("paying");
    setError("");
    try {
      settle(await send<Order>("POST", `/orders/${order.id}/demo-pay`));
    } catch (e) {
      setPhase("idle");
      setError(messageOf(e, "The payment didn't go through. No money was taken — try again."));
    }
  }

  async function payRazorpay() {
    setPhase("paying");
    setError("");
    try {
      await loadRazorpay();
    } catch {
      setPhase("idle");
      return setError("Couldn't load Razorpay. Check your connection (or an ad blocker) and try again.");
    }
    const rzp = new window.Razorpay!({
      key: order.key_id,
      order_id: order.razorpay_order_id,
      amount: order.total_paise,
      currency: "INR",
      name: "Frontrow",
      description: `${order.showtime.event.title} · ${order.seats.length} ${order.seats.length === 1 ? "seat" : "seats"}`,
      prefill: { name: order.customer.name, email: order.customer.email },
      notes: { order_id: order.id },
      theme: { color: "#E63946" },
      modal: { ondismiss: () => setPhase((p) => (p === "paying" ? "idle" : p)) },
      handler: async (r: RazorpayResponse) => {
        setPhase("confirming");
        try {
          settle(
            await send<Order>("POST", `/orders/${order.id}/verify`, {
              razorpay_payment_id: r.razorpay_payment_id,
              razorpay_signature: r.razorpay_signature,
            }),
          );
        } catch (e) {
          // A bad signature or a network blip: the webhook is the backstop — keep polling.
          if (!(e instanceof ApiRequestError && e.status === 400)) return;
          setPhase("idle");
          setError("We couldn't verify that payment. If money left your account it will be refunded automatically.");
        }
      },
    });
    rzp.on("payment.failed", (r) => {
      setError(`${r.error?.description ?? "The payment failed"}. No money was taken — try again.`);
    });
    rzp.open();
  }

  const { weekday, date } = dayParts(order.showtime.starts_at);
  const tiers = Object.values(
    order.seats.reduce<Record<string, { label: string; n: number; paise: number }>>((acc, s) => {
      const t = (acc[s.tier_key] ??= { label: s.tier_label, n: 0, paise: 0 });
      t.n += 1;
      t.paise += s.price_paise;
      return acc;
    }, {}),
  );
  const pending = order.status === "pending";
  const holdLapsed = pending && !holdClock.active;
  const busy = phase === "paying" || phase === "confirming" || phase === "torn";

  return (
    <div className="mx-auto grid w-[min(1100px,100%-32px)] gap-8 py-8 lg:grid-cols-[1fr_420px] lg:items-start lg:py-12">
      <div className="grid content-start gap-4">
        <p className="font-cond text-lg font-bold tracking-[.14em] text-amber uppercase">
          {pending ? "Checkout" : order.status === "paid" ? "Paid" : "Order"}
        </p>
        <h1 className="font-cond text-[clamp(40px,6vw,72px)] leading-[.92] font-extrabold uppercase">
          {order.status === "paid"
            ? "You're in"
            : order.status === "refunded"
              ? "Sorry — those seats went"
              : order.status === "expired"
                ? "This checkout expired"
                : order.status === "failed"
                  ? "The payment failed"
                  : "Pay to confirm your seats"}
        </h1>
        <Outcome order={order} holdLapsed={holdLapsed} />
      </div>

      <div className={cn("relative", phase === "torn" && "tk-tear")}>
        <section
          aria-label="Order summary"
          className="sm-stub rounded-card bg-paper text-ink shadow-[0_20px_50px_rgba(0,0,0,.45)]"
        >
          <div className="relative border-b-2 border-dashed border-ink/25 px-6 pt-5.5 pb-4 before:absolute before:-bottom-[11px] before:-left-[11px] before:size-[22px] before:rounded-full before:bg-plum after:absolute after:-right-[11px] after:-bottom-[11px] after:size-[22px] after:rounded-full after:bg-plum">
            <h2 className="pr-16 font-cond text-[34px] leading-[.95] font-extrabold uppercase">{order.showtime.event.title}</h2>
            <p className="mt-1 text-sm font-medium text-ink-2">{order.showtime.venue.name}</p>
            <span className="absolute top-5.5 right-6 rotate-[-6deg] rounded-sm border-2 border-red-dark px-2.5 py-1.5 font-cond text-sm font-extrabold tracking-[.14em] text-red-dark uppercase">
              {order.status === "paid" ? "Paid" : "Admit"}
            </span>
          </div>

          <div className="grid gap-4 px-6 py-4.5">
            <div className="grid grid-cols-2 gap-3 text-[13px] text-ink-2">
              <div>
                Date<b className="block font-cond text-[22px] font-bold tracking-[.02em] text-ink">{`${weekday} ${date}`}</b>
              </div>
              <div>
                Show<b className="block font-cond text-[22px] font-bold tracking-[.02em] text-ink">{showTime(order.showtime.starts_at)}</b>
              </div>
            </div>
            <div>
              <div className="mb-1.5 text-[13px] text-ink-2">Seats · {order.seats.length}</div>
              <ul className="flex list-none flex-wrap gap-1.5 p-0">
                {order.seats.map((s) => (
                  <li key={s.seat_id} className="rounded-chip bg-ink px-2.5 py-1.5 font-cond text-[17px] font-bold tracking-[.04em] text-paper">
                    {s.label}
                  </li>
                ))}
              </ul>
            </div>

            {pending && (
              <div className="flex items-baseline justify-between gap-3 rounded-lg bg-paper-2 px-3.5 py-3">
                <b className={cn("font-mono text-[30px] leading-none font-semibold tabular-nums", holdLapsed ? "text-ink-3" : "text-red-dark")}>
                  {holdLapsed ? payClock.text : holdClock.text}
                </b>
                <span className="text-right text-xs tracking-[.08em] text-ink-2 uppercase">
                  {holdLapsed ? "Hold lapsed · checkout closes in" : "Seats held for you"}
                </span>
              </div>
            )}

            <div className="grid gap-1.5 text-sm text-ink-2">
              {tiers.map((t) => (
                <div key={t.label} className="flex justify-between">
                  <span>
                    {t.n} × {t.label}
                  </span>
                  <span className="tabular-nums">{rupees(t.paise)}</span>
                </div>
              ))}
              <div className="flex justify-between">
                <span>Convenience fee · ₹30 per ticket</span>
                <span className="tabular-nums">{rupees(order.fee_paise)}</span>
              </div>
              <div className="mt-0.5 flex items-baseline justify-between border-t border-ink/20 pt-2 text-[17px] font-semibold text-ink">
                <span>{order.status === "refunded" ? "Refunded" : order.status === "paid" ? "Paid" : "Total"}</span>
                <b className="font-cond text-[30px] leading-none font-extrabold tabular-nums">{rupees(order.total_paise)}</b>
              </div>
            </div>
          </div>

          <div className="grid gap-2 px-6 pb-6">
            {pending && (
              <>
                {order.gateway === "demo" && (
                  <p className="rounded-btn border border-dashed border-ink/30 px-3 py-2 text-xs text-ink-2">
                    <b className="text-ink">Test payment.</b> This demo has no payment keys configured, so Pay confirms the order
                    through the same server path a Razorpay webhook takes. No money moves.
                  </p>
                )}
                {error && (
                  <p role="alert" className="rounded-btn bg-red-dark/10 px-3 py-2 text-sm font-medium text-red-dark">
                    {error}
                  </p>
                )}
                <Button className="w-full" disabled={busy} onClick={order.gateway === "razorpay" ? payRazorpay : payDemo}>
                  {phase === "confirming"
                    ? slow
                      ? "Payment received, confirming…"
                      : "Confirming…"
                    : phase === "paying"
                      ? "Opening payment…"
                      : `Pay ${rupees(order.total_paise)}${order.gateway === "demo" ? " · test" : ""}`}
                </Button>
                <p aria-live="polite" className="text-center text-xs text-ink-3">
                  {phase === "confirming"
                    ? slow
                      ? "Your bank has confirmed; we're waiting for the final word. Keep this page open."
                      : "Hold tight — issuing your tickets."
                    : order.gateway === "razorpay"
                      ? "Razorpay test mode · use card 4111 1111 1111 1111, any future date, any CVV"
                      : "Signed in as " + order.customer.email}
                </p>
              </>
            )}
            {order.status === "paid" && (
              <Link href={`/tickets/${order.id}`} className={buttonVariants({ className: "w-full" })}>
                See your tickets
              </Link>
            )}
            {(order.status === "refunded" || order.status === "expired" || order.status === "failed") && (
              <Link href={`/book/${order.showtime.id}`} className={buttonVariants({ className: "w-full" })}>
                Pick seats again
              </Link>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}

function Outcome({ order, holdLapsed }: { order: Order; holdLapsed: boolean }) {
  const p = "max-w-[52ch] text-lg text-muted-foreground";
  switch (order.status) {
    case "pending":
      return holdLapsed ? (
        <p className={p}>
          Your 10-minute hold has lapsed, but you can still pay until checkout closes. If the seats are still free, they&apos;re
          yours; if someone else bought one meanwhile, you&apos;re refunded in full automatically.
        </p>
      ) : (
        <p className={p}>
          Your seats are held while the clock runs. Pay now and each seat gets its own QR ticket the moment the payment
          clears.
        </p>
      );
    case "paid":
      return <p className={p}>Payment received and your tickets are issued.</p>;
    case "refunded":
      return (
        <p className={p}>
          Your hold ran out before the payment arrived, and in the meantime someone else bought{" "}
          {order.seats.length === 1 ? "that seat" : "one of those seats"}. We never sell a seat twice, so we refunded your{" "}
          {rupees(order.total_paise)} in full — it reaches your account in 5–7 working days.
        </p>
      );
    case "expired":
      return (
        <p className={p}>
          Checkout stays open for 15 minutes. Nothing was charged and the seats went back on sale — they may still be free.
        </p>
      );
    case "failed":
      return <p className={p}>No money was taken. Pick your seats again to retry.</p>;
  }
}
