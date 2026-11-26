import Link from "next/link";
import { dateTime } from "@/components/organiser/format";
import { CancelShowtime, EventFilter } from "@/components/organiser/ShowtimeActions";
import { Empty, FillBar, PageHead, StatusBadge } from "@/components/organiser/ui";
import { buttonVariants } from "@/components/ui/button";
import { api } from "@/lib/api";
import { rupees } from "@/lib/format";
import type { OrganiserShowtime } from "@/lib/types";

export const metadata = { title: "Showtimes" };

type Props = { searchParams: Promise<{ event_id?: string; created?: string }> };

/** S12 · showtimes, upcoming then played, with sales and the cancel guard. */
export default async function ShowtimesPage({ searchParams }: Props) {
  const { event_id, created } = await searchParams;
  const [events, showtimes] = await Promise.all([
    api("/organiser/events", { auth: true }),
    api("/organiser/showtimes", { auth: true, searchParams: { event_id } }),
  ]);
  const now = Date.now();
  const upcoming = showtimes.filter((s) => new Date(s.starts_at).getTime() > now);
  const past = showtimes.filter((s) => new Date(s.starts_at).getTime() <= now).reverse();
  const fresh = created ? showtimes.find((s) => s.id === created) : undefined;
  const newHref = `/organiser/showtimes/new${event_id ? `?event_id=${event_id}` : ""}`;

  return (
    <>
      <PageHead
        title="Showtimes"
        sub={`${upcoming.filter((s) => s.status === "scheduled").length} on sale · ${past.length} played`}
        action={
          <div className="flex flex-wrap items-center gap-3">
            {events.length > 0 && <EventFilter events={events} value={event_id} />}
            <Link href={newHref} className={buttonVariants({ size: "sm" })}>
              New showtime
            </Link>
          </div>
        }
      />
      {fresh && (
        <p role="status" className="mb-5 rounded-card border border-classic/40 bg-classic/10 px-4 py-3 text-sm">
          {fresh.event.title} at {fresh.venue.name}, {dateTime(fresh.starts_at)} is scheduled.{" "}
          {fresh.event.status === "live" ? (
            <Link href={`/book/${fresh.id}`} className="font-semibold underline underline-offset-4">
              Open its seat map ↗
            </Link>
          ) : (
            <Link href={`/organiser/events/${fresh.event.id}`} className="font-semibold underline underline-offset-4">
              Publish the event to make it bookable
            </Link>
          )}
        </p>
      )}
      {showtimes.length ? (
        <>
          <Group title="Upcoming" rows={upcoming} />
          {past.length > 0 && <Group title="Played" rows={past} past />}
        </>
      ) : (
        <Empty
          title="Nothing scheduled"
          body="A showtime puts an event on sale at one of your venues, with a price per seat tier."
          href={newHref}
          cta="Schedule a showtime"
        />
      )}
    </>
  );
}

function Group({ title, rows, past = false }: { title: string; rows: OrganiserShowtime[]; past?: boolean }) {
  return (
    <section aria-label={title} className="mb-8">
      <h2 className="mb-3 font-cond text-2xl font-bold uppercase">{title}</h2>
      {rows.length === 0 ? (
        <p className="rounded-card bg-plum-2 px-5 py-4 text-muted-foreground">Nothing upcoming for this filter.</p>
      ) : (
        <ul className="grid list-none gap-2.5 p-0">
          {rows.map((s) => {
            const cancelled = s.status === "cancelled";
            const status = cancelled ? "cancelled" : past ? "past" : s.event.status === "draft" ? "draft" : "scheduled";
            return (
              <li key={s.id} className="grid gap-3 rounded-card bg-plum-2 p-4 lg:grid-cols-[1.3fr_1fr_200px_auto] lg:items-center">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <b className="font-cond text-[22px] leading-tight font-bold">{s.event.title}</b>
                    <StatusBadge status={status} />
                  </div>
                  <p className="text-sm text-muted-foreground">
                    {dateTime(s.starts_at)} · {s.venue.name}
                  </p>
                </div>
                <p className="text-xs text-faint">
                  {s.tiers.length ? s.tiers.map((t) => `${t.label} ${rupees(t.price_paise)}`).join(" · ") : "No tiers on sale"}
                </p>
                <div>
                  <FillBar sold={s.sold} total={s.seat_count} />
                  <span className="text-xs text-muted-foreground">{rupees(s.revenue_paise)} revenue</span>
                </div>
                <div className="flex flex-wrap items-center gap-1.5 lg:justify-end">
                  <Link href={`/organiser/bookings/${s.id}`} className={buttonVariants({ variant: "outline", size: "sm" })}>
                    Bookings
                  </Link>
                  {!past && !cancelled && s.event.status === "live" && (
                    <Link href={`/book/${s.id}`} className={buttonVariants({ variant: "ghost", size: "sm" })}>
                      Seat map ↗
                    </Link>
                  )}
                  {!past && !cancelled && <CancelShowtime id={s.id} title={s.event.title} />}
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
