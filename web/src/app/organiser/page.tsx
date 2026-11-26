import Link from "next/link";
import { dateTime } from "@/components/organiser/format";
import { Card, FillBar, PageHead, Stat } from "@/components/organiser/ui";
import { buttonVariants } from "@/components/ui/button";
import { api } from "@/lib/api";
import { rupees } from "@/lib/format";
import { cn } from "@/lib/utils";

export const metadata = { title: "Overview" };

/** Console home: the numbers, the next shows, and a getting-started path for a new organiser. */
export default async function Overview() {
  const [venues, events, showtimes] = await Promise.all([
    api("/organiser/venues", { auth: true }),
    api("/organiser/events", { auth: true }),
    api("/organiser/showtimes", { auth: true }),
  ]);
  const now = Date.now();
  const upcoming = showtimes.filter((s) => s.status === "scheduled" && new Date(s.starts_at).getTime() > now);
  const sold = showtimes.reduce((a, s) => a + s.sold, 0);
  const revenue = showtimes.reduce((a, s) => a + s.revenue_paise, 0);
  const live = events.filter((e) => e.status === "live").length;

  const steps = [
    { done: venues.length > 0, title: "Add a venue", body: "Pick a template — cinema grid, stalls + balcony or arena — and tune it.", href: "/organiser/venues/new" },
    { done: events.length > 0, title: "Create an event", body: "Title, poster, synopsis. Publish it live or keep it as a draft.", href: "/organiser/events/new" },
    { done: showtimes.length > 0, title: "Schedule a showtime", body: "Event + venue + start time + a price per tier. It's bookable at once.", href: "/organiser/showtimes/new" },
  ];
  const fresh = steps.some((s) => !s.done);

  return (
    <>
      <PageHead
        title="Overview"
        sub="Sales from every showtime you run. Bookings update as customers pay."
        action={
          <Link href="/organiser/showtimes/new" className={buttonVariants({ size: "sm" })}>
            New showtime
          </Link>
        }
      />

      {fresh && (
        <section aria-labelledby="start" className="mb-8 rounded-card bg-paper p-5 text-ink sm:p-6">
          <h2 id="start" className="font-cond text-3xl font-extrabold uppercase">
            Get your first show on sale
          </h2>
          <p className="mt-1 text-sm text-ink-2">Three steps, about three minutes.</p>
          <ol className="mt-4 grid list-none gap-3 p-0 md:grid-cols-3">
            {steps.map((s, i) => (
              <li key={s.title} className={cn("rounded-card border-2 p-4", s.done ? "border-ink/10 opacity-70" : "border-ink/25")}>
                <div className="flex items-center gap-2 font-cond text-xl font-bold uppercase">
                  <span
                    aria-hidden="true"
                    className={cn(
                      "grid size-7 place-items-center rounded-full text-base",
                      s.done ? "bg-ink text-paper" : "border-2 border-ink/40",
                    )}
                  >
                    {s.done ? "✓" : i + 1}
                  </span>
                  {s.title}
                  {s.done && <span className="sr-only">(done)</span>}
                </div>
                <p className="mt-1.5 text-sm text-ink-2">{s.body}</p>
                {!s.done && (
                  <Link href={s.href} className={cn(buttonVariants({ variant: "ink", size: "sm" }), "mt-3")}>
                    {s.title}
                  </Link>
                )}
              </li>
            ))}
          </ol>
        </section>
      )}

      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        <Stat label="Venues" value={venues.length} hint={`${venues.reduce((a, v) => a + v.seat_count, 0).toLocaleString("en-IN")} seats`} />
        <Stat label="Live events" value={live} hint={`${events.length - live} draft`} />
        <Stat label="Upcoming shows" value={upcoming.length} />
        <Stat label="Tickets sold" value={sold.toLocaleString("en-IN")} />
        <Stat label="Revenue" value={rupees(revenue)} hint="tickets, excl. fees" />
      </div>

      <section aria-labelledby="next" className="mt-10">
        <div className="mb-3 flex items-baseline justify-between gap-4">
          <h2 id="next" className="font-cond text-3xl font-extrabold uppercase">
            Next up
          </h2>
          <Link href="/organiser/showtimes" className="text-sm text-muted-foreground hover:text-screen">
            All showtimes →
          </Link>
        </div>
        {upcoming.length ? (
          <ul className="grid list-none gap-2.5 p-0">
            {upcoming.slice(0, 6).map((s) => (
              <li key={s.id}>
                <Card className="grid gap-3 sm:grid-cols-[1fr_220px_auto] sm:items-center">
                  <div>
                    <b className="block font-cond text-[22px] leading-tight font-bold">{s.event.title}</b>
                    <span className="text-sm text-muted-foreground">
                      {dateTime(s.starts_at)} · {s.venue.name}
                    </span>
                  </div>
                  <FillBar sold={s.sold} total={s.seat_count} />
                  <Link href={`/organiser/bookings/${s.id}`} className={buttonVariants({ variant: "outline", size: "sm" })}>
                    Bookings · {rupees(s.revenue_paise)}
                  </Link>
                </Card>
              </li>
            ))}
          </ul>
        ) : (
          <p className="rounded-card bg-plum-2 px-5 py-4 text-muted-foreground">
            Nothing scheduled.{" "}
            <Link href="/organiser/showtimes/new" className="text-screen underline underline-offset-4">
              Schedule a showtime
            </Link>{" "}
            to open sales.
          </p>
        )}
      </section>
    </>
  );
}
