import Link from "next/link";
import { notFound } from "next/navigation";
import { dateTime, stamp } from "@/components/owner/format";
import { FillBar, PageHead, Stat, StatusBadge } from "@/components/owner/ui";
import { buttonVariants } from "@/components/ui/button";
import { api, ApiRequestError } from "@/lib/api";
import { rupees } from "@/lib/format";

export const metadata = { title: "Bookings" };

type Props = { params: Promise<{ id: string }> };

/** O7 · every paid booking for one show, with CSV export. */
export default async function BookingsPage({ params }: Props) {
  const { id } = await params;
  let data;
  try {
    data = await api("/owner/shows/{show_id}/bookings", { params: { show_id: id }, auth: true });
  } catch (e) {
    if (e instanceof ApiRequestError && e.status === 404) notFound();
    throw e;
  }
  const { show, bookings } = data;
  const played = new Date(show.ends_at).getTime() < Date.now();
  const scanned = bookings.reduce((a, b) => a + b.checked_in, 0);
  return (
    <>
      <PageHead
        title={show.film.title}
        sub={
          <span className="inline-flex flex-wrap items-center gap-2">
            {dateTime(show.starts_at)} · {show.cinema_name} · {show.screen_name} · {show.language} {show.format}
            <StatusBadge status={show.status === "cancelled" ? "cancelled" : played ? "past" : show.public ? "public" : "private"} />
          </span>
        }
        back={{ href: `/owner/shows?date=${new Date(show.starts_at).toLocaleDateString("en-CA", { timeZone: "Asia/Kolkata" })}`, label: "Shows" }}
        action={
          <div className="flex flex-wrap gap-2">
            <Link href={`/owner/checkin/${show.id}`} className={buttonVariants({ size: "sm" })}>
              Open the door
            </Link>
            {bookings.length > 0 && (
              <a href={`/api/owner/shows/${show.id}/bookings?format=csv`} download className={buttonVariants({ variant: "paper", size: "sm" })}>
                Download CSV
              </a>
            )}
          </div>
        }
      />
      <div className="mb-8 grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Bookings" value={bookings.length} />
        <Stat label="Tickets" value={show.sold.toLocaleString("en-IN")} hint={`${scanned} scanned in`} />
        <Stat label="Sales" value={rupees(show.revenue_paise)} hint="tickets, excl. Frontrow's fee" />
        <div className="rounded-card border border-border bg-plum-2 px-4 py-3.5">
          <div className="mb-2 text-xs font-semibold tracking-[.1em] text-muted-foreground uppercase">Fill</div>
          <FillBar sold={show.sold} total={show.seat_count} />
        </div>
      </div>

      {bookings.length ? (
        <div className="overflow-x-auto rounded-card border border-border bg-plum-2">
          <table className="w-full min-w-[920px] border-collapse text-left text-sm">
            <caption className="sr-only">Paid bookings, in the order they were paid</caption>
            <thead>
              <tr className="border-b border-border text-xs tracking-[.08em] text-ink-2 uppercase">
                <th scope="col" className="px-4 py-3 font-semibold">Booking</th>
                <th scope="col" className="px-4 py-3 font-semibold">Customer</th>
                <th scope="col" className="px-4 py-3 font-semibold">Seats</th>
                <th scope="col" className="px-4 py-3 font-semibold">Tier</th>
                <th scope="col" className="px-4 py-3 text-right font-semibold">Amount</th>
                <th scope="col" className="px-4 py-3 font-semibold">Payment</th>
                <th scope="col" className="px-4 py-3 font-semibold">Paid</th>
                <th scope="col" className="px-4 py-3 text-right font-semibold">In</th>
              </tr>
            </thead>
            <tbody>
              {bookings.map((b) => (
                <tr key={b.order_id} className="border-b border-border last:border-0">
                  <td className="px-4 py-3 font-mono text-xs">{b.order_id.slice(0, 8).toUpperCase()}</td>
                  <td className="px-4 py-3">
                    <b className="block font-semibold">{b.name}</b>
                    <span className="text-xs text-ink-2">{b.email}</span>
                  </td>
                  <td className="px-4 py-3 font-cond text-[17px] font-bold tracking-[.03em]">{b.seats.join(", ")}</td>
                  <td className="px-4 py-3 text-ink-2">{b.tier_labels.join(" / ")}</td>
                  <td className="px-4 py-3 text-right font-semibold tabular-nums">{rupees(b.amount_paise)}</td>
                  <td className="px-4 py-3 text-ink-2">{b.payment_method ?? "—"}</td>
                  <td className="px-4 py-3 whitespace-nowrap text-ink-2">{stamp(b.paid_at)}</td>
                  <td className="px-4 py-3 text-right tabular-nums">
                    {b.checked_in}/{b.seats.length}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="grid justify-items-start gap-3 rounded-card border border-dashed border-ink/25 px-6 py-8">
          <h2 className="font-cond text-2xl font-bold uppercase">No bookings yet</h2>
          <p className="max-w-[52ch] text-muted-foreground">
            Paid bookings appear here the moment a payment is confirmed.
            {!show.public && " This show isn't public yet, so customers can't book it."}
          </p>
          {show.public && !played && (
            <Link href={`/book/${show.id}`} className={buttonVariants({ size: "sm" })}>
              Open the seat map
            </Link>
          )}
        </div>
      )}
    </>
  );
}
