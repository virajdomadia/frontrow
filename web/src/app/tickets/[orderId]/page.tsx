import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { notFound } from "next/navigation";
import QRCode from "qrcode";
import { CalendarPlus, MapPin, Ticket as TicketIcon } from "lucide-react";
import { FlowHeader } from "@/components/booking/FlowHeader";
import { PrintButton } from "@/components/tickets/PrintButton";
import { buttonVariants } from "@/components/ui/button";
import { api, ApiRequestError } from "@/lib/api";
import { googleCalendarUrl } from "@/lib/calendar";
import { dayParts, duration, rupees, showTime, when } from "@/lib/format";
import { requireMe } from "@/lib/session";
import { SITE_URL } from "@/lib/site";
import { cn } from "@/lib/utils";

export const metadata: Metadata = { title: "Your tickets", robots: { index: false } };

type Props = { params: Promise<{ orderId: string }> };

/** The QR as inline SVG, drawn on the server — no client JS, crisp at any size, prints cleanly. */
function qrSvg(token: string) {
  return QRCode.toString(token, {
    type: "svg",
    errorCorrectionLevel: "M",
    margin: 1,
    color: { dark: "#2A0B1E", light: "#FFFBF4" },
  });
}

/** C9 · M-ticket: one ticket per seat with its signed QR, the receipt, calendar, directions, print. */
export default async function TicketsPage({ params }: Props) {
  const { orderId } = await params;
  await requireMe(`/tickets/${orderId}`);
  let bundle;
  try {
    bundle = await api("/tickets/{order_id}", { params: { order_id: orderId }, auth: true });
  } catch (e) {
    if (e instanceof ApiRequestError && e.status === 404) notFound();
    throw e;
  }
  const { order, tickets } = bundle;
  const st = order.show;
  const qrs = await Promise.all(tickets.map((t) => qrSvg(t.qr_token)));
  const { weekday, date } = dayParts(st.starts_at);
  const past = new Date(st.ends_at).getTime() < Date.now();
  const receipt = Object.values(
    order.seats.reduce<Record<string, { label: string; n: number; paise: number }>>((acc, s) => {
      const r = (acc[s.tier_key] ??= { label: s.tier_label, n: 0, paise: 0 });
      r.n += 1;
      r.paise += s.price_paise;
      return acc;
    }, {}),
  );
  const entry = {
    uid: order.id,
    title: st.film.title,
    start: st.starts_at,
    end: st.ends_at,
    location: `${st.cinema.name}, ${st.cinema.address}`,
    description: `Frontrow tickets — seats ${order.seats.map((s) => s.label).join(", ")}`,
    url: `${SITE_URL}/tickets/${order.id}`,
  };
  const directions = `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(`${st.cinema.name}, ${st.cinema.address}`)}`;

  return (
    <>
      <FlowHeader step={2} back="/my-tickets" backLabel="My tickets" />
      <main className="mx-auto grid w-[min(1100px,100%-32px)] gap-8 py-8 lg:py-12">
        <div className="tk-rise grid gap-5 lg:grid-cols-[1fr_auto] lg:items-end">
          <div className="grid gap-3">
            <p className="font-cond text-lg font-bold tracking-[.14em] text-red-dark uppercase">
              {past ? "Played" : `${tickets.length} ${tickets.length === 1 ? "ticket" : "tickets"} · paid ${rupees(order.total_paise)}`}
            </p>
            <h1 className="font-cond text-[clamp(44px,7vw,84px)] leading-[.9] font-extrabold uppercase">
              {past ? st.film.title : "You're in"}
            </h1>
            <p className="max-w-[56ch] text-lg text-muted-foreground">
              {st.film.title} · {when(st.starts_at)} · {st.cinema.name} · {st.screen_name}. Show the QR for each seat at the
              door — one scan per seat. Screenshots work too. A confirmation email with this link was sent to {order.customer.email}.
            </p>
          </div>
          <div className="no-print flex flex-wrap gap-2">
            {!past && (
              <>
                <a href={`/tickets/${order.id}/calendar.ics`} download className={buttonVariants({ variant: "outline", size: "sm" })}>
                  <CalendarPlus aria-hidden="true" /> Add to calendar
                </a>
                <a href={googleCalendarUrl(entry)} target="_blank" rel="noopener noreferrer" className={buttonVariants({ variant: "outline", size: "sm" })}>
                  Google Calendar
                </a>
              </>
            )}
            <a href={directions} target="_blank" rel="noopener noreferrer" className={buttonVariants({ variant: "outline", size: "sm" })}>
              <MapPin aria-hidden="true" /> Directions
            </a>
            <PrintButton />
          </div>
        </div>

        <ol className="grid list-none gap-5 p-0">
          {tickets.map((t, i) => (
            <li
              key={t.id}
              className="tk-rise relative grid overflow-hidden rounded-card border border-border bg-paper text-ink shadow-[0_20px_50px_rgb(42_11_30_/_.14)] sm:grid-cols-[1fr_220px]"
              style={{ animationDelay: `${120 + i * 90}ms` }}
            >
              <div className="grid gap-4 p-5 sm:p-6">
                <div className="flex items-start gap-4">
                  <Image
                    src={st.film.poster_url}
                    alt=""
                    width={64}
                    height={88}
                    sizes="64px"
                    className="hidden h-[88px] w-16 rounded-[6px] object-cover sm:block"
                  />
                  <div>
                    <h2 className="font-cond text-[34px] leading-[.95] font-extrabold uppercase">{st.film.title}</h2>
                    <p className="mt-1 text-sm font-medium text-ink-2">
                      {st.cinema.name} · {st.screen_name} · {st.language} {st.format}
                    </p>
                  </div>
                </div>
                <dl className="grid grid-cols-2 gap-x-5 gap-y-3 text-[13px] text-ink-2 sm:grid-cols-4">
                  <div>
                    <dt>Date</dt>
                    <dd className="m-0 font-cond text-[22px] font-bold text-ink">{`${weekday} ${date}`}</dd>
                  </div>
                  <div>
                    <dt>Show</dt>
                    <dd className="m-0 font-cond text-[22px] font-bold text-ink">{showTime(st.starts_at)}</dd>
                  </div>
                  <div>
                    <dt>Seat</dt>
                    <dd className="m-0 font-cond text-[22px] font-bold text-red-dark">{t.label}</dd>
                  </div>
                  <div>
                    <dt>Tier</dt>
                    <dd className="m-0 font-cond text-[22px] font-bold text-ink">{t.tier_label}</dd>
                  </div>
                </dl>
                <p className="flex flex-wrap gap-x-4 text-xs text-ink-3">
                  <span>
                    Ticket {i + 1} of {tickets.length}
                  </span>
                  <span>{duration(st.film.runtime_min)}</span>
                  <span>{st.film.cert ? `Rated ${st.film.cert}` : "Not yet certified"}</span>
                  <span className="font-mono">#{t.id.slice(0, 8).toUpperCase()}</span>
                </p>
              </div>
              <div className="relative grid place-items-center gap-2 border-t-2 border-dashed border-ink/25 p-5 sm:border-t-0 sm:border-l-2 sm:before:absolute sm:before:-top-[11px] sm:before:-left-[11px] sm:before:size-[22px] sm:before:rounded-full sm:before:bg-plum sm:after:absolute sm:after:-bottom-[11px] sm:after:-left-[11px] sm:after:size-[22px] sm:after:rounded-full sm:after:bg-plum">
                <div
                  role="img"
                  aria-label={`QR code for seat ${t.label}`}
                  className={cn("tk-qr w-[min(180px,60vw)]", t.checked_in_at && "opacity-30")}
                  // The SVG comes from the qrcode library, built from our own signed token.
                  dangerouslySetInnerHTML={{ __html: qrs[i] }}
                />
                <span className="flex items-center gap-1.5 font-cond text-sm font-bold tracking-[.12em] text-ink-2 uppercase">
                  <TicketIcon aria-hidden="true" className="size-4" />
                  {t.checked_in_at ? `Checked in ${showTime(t.checked_in_at)}` : "Admit one"}
                </span>
                {!t.checked_in_at && !past && (
                  <details className="no-print w-full text-center text-[11px] text-ink-3">
                    <summary className="cursor-pointer">Code (if the scanner can&apos;t read the QR)</summary>
                    <code className="mt-1 block font-mono break-all select-all">{t.qr_token}</code>
                  </details>
                )}
              </div>
            </li>
          ))}
        </ol>

        <section aria-labelledby="receipt" className="fr-stub grid gap-2 p-5 text-sm sm:max-w-[460px]">
          <h2 id="receipt" className="font-cond text-2xl font-bold uppercase">
            Receipt
          </h2>
          <p className="text-ink-2">
            Booking ID <b className="font-mono text-ink">{order.id.slice(0, 8).toUpperCase()}</b>
            {order.paid_at && <> · paid {when(order.paid_at)}</>}
          </p>
          {receipt.map((r) => (
            <div key={r.label} className="flex justify-between text-ink-2">
              <span>
                {r.n} × {r.label}
              </span>
              <span className="tabular-nums">{rupees(r.paise)}</span>
            </div>
          ))}
          <div className="flex justify-between text-ink-2">
            <span>Convenience fee · ₹30 per ticket</span>
            <span className="tabular-nums">{rupees(order.fee_paise)}</span>
          </div>
          <div className="flex items-baseline justify-between border-t border-ink/20 pt-2 font-semibold">
            <span>Paid · {order.payment_method ?? "Online"}</span>
            <b className="font-cond text-2xl tabular-nums">{rupees(order.total_paise)}</b>
          </div>
        </section>

        <div className="no-print flex flex-wrap items-center justify-between gap-4 border-t border-border pt-6 text-sm text-muted-foreground">
          <span>Signed in as {order.customer.email}</span>
          <span className="flex gap-4">
            <Link href="/my-tickets" className="text-screen underline underline-offset-4">
              All my tickets
            </Link>
            <Link href="/movies" className="text-screen underline underline-offset-4">
              Book another show
            </Link>
          </span>
        </div>
      </main>
    </>
  );
}
