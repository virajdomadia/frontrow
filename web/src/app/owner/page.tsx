import Link from "next/link";
import { dayName } from "@/components/owner/format";
import { ShowsTable } from "@/components/owner/ShowsTable";
import { Empty, PageHead, Stat, StatusBadge } from "@/components/owner/ui";
import { buttonVariants } from "@/components/ui/button";
import { api } from "@/lib/api";
import { rupees } from "@/lib/format";
import { cn } from "@/lib/utils";

export const metadata = { title: "Overview" };

/** The console's front page: status, the setup checklist, and today's shows with their doors. */
export default async function OwnerOverview() {
  const [business, today] = await Promise.all([api("/owner/business", { auth: true }), api("/owner/shows", { auth: true })]);
  const steps = [
    { done: business.cinema_count > 0, title: "Add a cinema", body: "Name, area, address, facilities.", href: "/owner/cinemas/new" },
    { done: business.screen_count > 0, title: "Add screens", body: "From a template, with a live seat-map preview.", href: "/owner/cinemas" },
    { done: business.upcoming_shows > 0, title: "Schedule shows", body: "Pick a film, days, times and prices.", href: "/owner/shows/new" },
    { done: business.status === "verified", title: "Get verified", body: "Frontrow staff approve you once; then you're public.", href: undefined },
  ];
  const sold = today.shows.reduce((a, s) => a + s.sold, 0);
  const revenue = today.shows.reduce((a, s) => a + s.revenue_paise, 0);
  const now = Date.now();
  const next = today.dates.find((d) => d.show_count > 0 && d.date > today.date);

  return (
    <>
      <PageHead
        title={business.name}
        sub={
          <span className="inline-flex flex-wrap items-center gap-2">
            <StatusBadge status={business.status} /> {business.cinema_count} cinema{business.cinema_count === 1 ? "" : "s"} ·{" "}
            {business.screen_count} screen{business.screen_count === 1 ? "" : "s"} · {business.upcoming_shows} upcoming shows
          </span>
        }
        action={
          <Link href="/owner/shows/new" className={buttonVariants()}>
            Schedule shows
          </Link>
        }
      />

      {steps.some((s) => !s.done) && (
        <section aria-labelledby="setup" className="mb-10">
          <h2 id="setup" className="mb-3 font-cond text-2xl font-bold uppercase">
            Set up
          </h2>
          <ol className="grid list-none gap-3 p-0 sm:grid-cols-2 lg:grid-cols-4">
            {steps.map((s, i) => (
              <li key={s.title} className={cn("rounded-card border p-4", s.done ? "border-border bg-plum-2" : "border-ink/30 bg-paper")}>
                <span className={cn("font-cond text-sm font-bold tracking-[.1em] uppercase", s.done ? "text-[#1f6e57]" : "text-ink-3")}>
                  {s.done ? "✓ Done" : `Step ${i + 1}`}
                </span>
                <h3 className="mt-1 font-cond text-xl font-bold uppercase">{s.title}</h3>
                <p className="mt-1 text-sm text-ink-2">{s.body}</p>
                {!s.done && s.href && (
                  <Link href={s.href} className={cn(buttonVariants({ variant: "paper", size: "sm" }), "mt-3")}>
                    {s.title}
                  </Link>
                )}
              </li>
            ))}
          </ol>
        </section>
      )}

      <div className="mb-6 grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Shows today" value={today.shows.length} />
        <Stat label="Tickets sold today" value={sold.toLocaleString("en-IN")} />
        <Stat label="Today's sales" value={rupees(revenue)} hint="tickets, excl. Frontrow's fee" />
        <Stat label="Upcoming shows" value={business.upcoming_shows} hint="next 14 days and beyond" />
      </div>

      <div className="mb-3 flex flex-wrap items-end justify-between gap-3">
        <h2 className="font-cond text-3xl font-bold uppercase">Today</h2>
        <Link href="/owner/shows" className="text-sm font-semibold underline underline-offset-4">
          All days →
        </Link>
      </div>
      {today.shows.length ? (
        <ShowsTable shows={today.shows} now={now} />
      ) : (
        <Empty
          title="No shows today"
          body={
            next
              ? `${business.upcoming_shows} upcoming shows. The next day with shows is ${dayName(next.date)}.`
              : "Schedule a film on one of your screens — a day, a week or a month of shows in one go."
          }
          href={next ? `/owner/shows?date=${next.date}` : "/owner/shows/new"}
          cta={next ? `See ${dayName(next.date)} · ${next.show_count} shows` : "Schedule shows"}
        />
      )}
    </>
  );
}
