import Link from "next/link";
import { notFound } from "next/navigation";
import { dateTime, stamp } from "@/components/organiser/format";
import { FillBar, PageHead, Stat, StatusBadge } from "@/components/organiser/ui";
import { buttonVariants } from "@/components/ui/button";
import { api, ApiRequestError } from "@/lib/api";
import { rupees } from "@/lib/format";

export const metadata = { title: "Bookings" };

type Props = { params: Promise<{ showtimeId: string }> };

/** S13 · paid orders for one showtime, with CSV export. (The live dashboard is v2.) */
export default async function BookingsPage({ params }: Props) {
  const { showtimeId } = await params;
  let data;
  try {
    data = await api("/organiser/showtimes/{showtime_id}/bookings", { params: { showtime_id: showtimeId }, auth: true });
  } catch (e) {
    if (e instanceof ApiRequestError && e.status === 404) notFound();
    throw e;
  }
  const { showtime, bookings } = data;
  const past = new Date(showtime.starts_at).getTime() <= Date.now();
  const selling = showtime.status === "scheduled" && !past && showtime.event.status === "live";
  return (
    <>
      <PageHead
        title={showtime.event.title}
        sub={
          <span className="inline-flex flex-wrap items-center gap-2">
            {dateTime(showtime.starts_at)} · {showtime.venue.name}
            <StatusBadge status={showtime.status === "cancelled" ? "cancelled" : past ? "past" : "scheduled"} />
          </span>
        }
        back={{ href: `/organiser/showtimes?event_id=${showtime.event.id}`, label: "Showtimes" }}
        action={
          bookings.length > 0 && (
            <a href={`/api/organiser/showtimes/${showtime.id}/bookings?format=csv`} download className={buttonVariants({ size: "sm" })}>
              Download CSV
            </a>
          )
        }
      />
      <div className="mb-8 grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Orders" value={bookings.length} />
        <Stat label="Tickets" value={data.tickets.toLocaleString("en-IN")} />
        <Stat label="Revenue" value={rupees(data.revenue_paise)} hint="tickets, excl. fees" />
        <div className="rounded-card bg-plum-2 px-4 py-3.5">
          <div className="mb-2 text-xs font-semibold tracking-[.1em] text-muted-foreground uppercase">Fill</div>
          <FillBar sold={showtime.sold} total={showtime.seat_count} />
        </div>
      </div>

      {bookings.length ? (
        <div className="overflow-x-auto rounded-card bg-paper text-ink">
          <table className="w-full min-w-[760px] border-collapse text-left text-sm">
            <caption className="sr-only">Paid orders, newest first</caption>
            <thead>
              <tr className="border-b border-ink/15 text-xs tracking-[.08em] text-ink-2 uppercase">
                <th scope="col" className="px-4 py-3 font-semibold">Customer</th>
                <th scope="col" className="px-4 py-3 font-semibold">Seats</th>
                <th scope="col" className="px-4 py-3 font-semibold">Tier</th>
                <th scope="col" className="px-4 py-3 text-right font-semibold">Tickets</th>
                <th scope="col" className="px-4 py-3 text-right font-semibold">Paid</th>
                <th scope="col" className="px-4 py-3 font-semibold">When</th>
              </tr>
            </thead>
            <tbody>
              {bookings.map((b) => (
                <tr key={b.order_id} className="border-b border-ink/10 last:border-0">
                  <td className="px-4 py-3">
                    <b className="block font-semibold">{b.customer_name}</b>
                    <span className="text-xs text-ink-2">{b.customer_email}</span>
                  </td>
                  <td className="px-4 py-3 font-cond text-[17px] font-bold tracking-[.03em]">{b.seats.join(", ")}</td>
                  <td className="px-4 py-3 text-ink-2">{b.tier_labels.join(" / ")}</td>
                  <td className="px-4 py-3 text-right tabular-nums">{b.tickets}</td>
                  <td className="px-4 py-3 text-right font-semibold tabular-nums">{rupees(b.total_paise)}</td>
                  <td className="px-4 py-3 whitespace-nowrap text-ink-2">{stamp(b.paid_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="grid justify-items-start gap-3 rounded-card border border-dashed border-screen/20 px-6 py-8">
          <h2 className="font-cond text-2xl font-bold uppercase">No bookings yet</h2>
          <p className="max-w-[52ch] text-muted-foreground">
            Paid orders appear here the moment a payment is confirmed.{selling && " Share the seat map to start selling."}
          </p>
          {selling && (
            <Link href={`/book/${showtime.id}`} className={buttonVariants({ size: "sm" })}>
              Open the seat map
            </Link>
          )}
        </div>
      )}
    </>
  );
}
