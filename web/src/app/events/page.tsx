import type { Metadata } from "next";
import Link from "next/link";
import { EventCard } from "@/components/events/EventCard";
import { Filters } from "@/components/events/Filters";
import { SiteFooter, SiteHeader, type NavKey } from "@/components/site/SiteHeader";
import { buttonVariants } from "@/components/ui/button";
import { api, ApiRequestError } from "@/lib/api";
import { eventsHref, readFilters, type Filters as F } from "@/lib/filters";
import { dayKey } from "@/lib/format";
import type { EventList } from "@/lib/types";

export const metadata: Metadata = {
  title: "Shows in Bengaluru",
  description: "Films and live concerts across Bengaluru. Filter by day, type, genre and venue, then pick your seat on a live map.",
  alternates: { canonical: "/events" },
};

const HEADINGS: Record<string, string> = { movie: "Movies in Bengaluru", concert: "Concerts in Bengaluru" };
const WHEN: Record<string, string> = { today: "today", tomorrow: "tomorrow", weekend: "this weekend" };

export default async function EventsPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const current = readFilters(await searchParams);
  const now = new Date();

  let list: EventList | null = null;
  let invalid = false;
  try {
    list = await api("/events", { searchParams: current, revalidate: 60, tags: ["events"] });
  } catch (e) {
    // A hand-edited query (?date=someday) is a 422 — show the empty state, not an error page.
    if (e instanceof ApiRequestError && e.status === 422) invalid = true;
    else throw e;
  }

  const active: NavKey | undefined =
    current.type === "movie" ? "movie" : current.type === "concert" ? "concert" : !current.type ? "all" : undefined;
  const filtered = Object.keys(current).some((k) => k !== "sort");

  return (
    <>
      <SiteHeader active={active} />
      <main className="mx-auto w-[min(1240px,100%-32px)] pt-7">
        <h1 className="font-cond text-[clamp(40px,6vw,64px)] leading-[.95] font-extrabold uppercase">
          {HEADINGS[current.type ?? ""] ?? "Shows in Bengaluru"}
        </h1>
        <Filters current={current} genres={list?.genres ?? []} venues={list?.venues ?? []} today={dayKey(now)} />

        {list && list.total > 0 ? (
          <>
            <p className="mt-3 text-[13px] text-faint" aria-live="polite">
              {summary(list, current)}
            </p>
            <ul className="mt-5 grid list-none grid-cols-2 gap-3 p-0 sm:grid-cols-3 sm:gap-4 lg:grid-cols-4 lg:gap-[18px]">
              {list.events.map((e, i) => (
                <li key={e.id} className="grid">
                  <EventCard event={e} now={now} priority={i < 4} />
                </li>
              ))}
            </ul>
          </>
        ) : (
          <Empty invalid={invalid} filtered={filtered} current={current} />
        )}
      </main>
      <SiteFooter />
    </>
  );
}

function summary(list: EventList, f: F) {
  const shows = `${list.total} ${list.total === 1 ? "show" : "shows"}`;
  const times = `${list.showtime_count} ${list.showtime_count === 1 ? "showtime" : "showtimes"}`;
  const when = f.date ? (WHEN[f.date] ?? `on ${f.date}`) : "coming up";
  return `${shows} · ${times} ${when}`;
}

function Empty({ invalid, filtered, current }: { invalid: boolean; filtered: boolean; current: F }) {
  return (
    <div className="mt-8 grid max-w-xl justify-items-start gap-3 rounded-card bg-plum-2 px-6 py-7">
      <h2 className="font-cond text-3xl leading-none font-bold uppercase">
        {invalid ? "That filter doesn't look right" : "Nothing on for that"}
      </h2>
      <p className="text-muted-foreground">
        {invalid
          ? "The link has a date or filter we can't read. Start again from everything that's on."
          : filtered
            ? "No showtimes match those filters. Try another day, or widen the genre or venue."
            : "The box office is quiet right now — new showtimes are added every week."}
      </p>
      {(filtered || invalid) && (
        <div className="mt-1 flex flex-wrap gap-2">
          {current.date && !invalid && (
            <Link href={eventsHref(current, { date: undefined })} className={buttonVariants({ size: "sm" })}>
              Any day
            </Link>
          )}
          <Link href="/events" className={buttonVariants({ variant: "outline", size: "sm" })}>
            Clear filters
          </Link>
        </div>
      )}
    </div>
  );
}
