import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { cache } from "react";
import { BookingView } from "@/components/booking/BookingView";
import { FlowHeader } from "@/components/booking/FlowHeader";
import { buttonVariants } from "@/components/ui/button";
import { api, ApiRequestError } from "@/lib/api";
import { when } from "@/lib/format";
import type { ShowtimeDetail } from "@/lib/types";

// The detail is catalog-fresh (60 s) and the layout immutable; the seat state is read per request
// with the viewer's cookie, so this page always renders dynamically. A showtime that has started
// or was cancelled is a 410 `showtime_closed` from the api, whose details carry what the page
// needs to say so; the start-time check below still covers a detail cached just before the start.
type Closed = { reason: string; slug: string; title: string; venue: string; startsAt: string };
type Loaded = { showtime: ShowtimeDetail; closed: null } | { showtime: null; closed: Closed } | null;

function closedFrom(e: unknown): Closed | null {
  if (!(e instanceof ApiRequestError && e.status === 410)) return null;
  const d = (e.body.details ?? {}) as Record<string, unknown>;
  const str = (k: string) => (typeof d[k] === "string" ? (d[k] as string) : "");
  return { reason: str("reason"), slug: str("event_slug"), title: str("event_title"), venue: str("venue_name"), startsAt: str("starts_at") };
}

const getShowtime = cache(async (id: string): Promise<Loaded> => {
  try {
    const showtime = await api("/showtimes/{showtime_id}", { params: { showtime_id: id }, revalidate: 60, tags: [`showtime:${id}`] });
    if (showtime.status === "cancelled" || new Date(showtime.starts_at).getTime() <= Date.now())
      return {
        showtime: null,
        closed: {
          reason: showtime.status === "cancelled" ? "cancelled" : "started",
          slug: showtime.event.slug,
          title: showtime.event.title,
          venue: showtime.venue.name,
          startsAt: showtime.starts_at,
        },
      };
    return { showtime, closed: null };
  } catch (e) {
    if (e instanceof ApiRequestError && e.status === 404) return null;
    const closed = closedFrom(e);
    if (closed) return { showtime: null, closed };
    throw e;
  }
});

type Props = { params: Promise<{ showtimeId: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const loaded = await getShowtime((await params).showtimeId);
  if (!loaded) return { title: "Show not found", robots: { index: false } };
  if (loaded.closed) return { title: `Closed · ${loaded.closed.title}`, robots: { index: false } };
  const { showtime } = loaded;
  return {
    title: `Pick seats · ${showtime.event.title}`,
    description: `${showtime.event.title} at ${showtime.venue.name}, ${when(showtime.starts_at)}. Pick your seats on the live map.`,
    robots: { index: false },
  };
}

export default async function BookPage({ params }: Props) {
  const { showtimeId } = await params;
  const loaded = await getShowtime(showtimeId);
  if (!loaded) notFound();

  let closed = loaded.closed;
  let ready = null;
  if (loaded.showtime) {
    const showtime = loaded.showtime;
    try {
      const [layout, snapshot] = await Promise.all([
        api("/venues/{venue_id}/layout", { params: { venue_id: showtime.venue.id }, revalidate: 86_400, tags: [`venue:${showtime.venue.id}`] }),
        api("/showtimes/{showtime_id}/seats", { params: { showtime_id: showtime.id }, auth: true }),
      ]);
      ready = { showtime, layout, snapshot };
    } catch (e) {
      closed = closedFrom(e); // it started between the two reads
      if (!closed) throw e;
    }
  }

  return (
    <>
      <FlowHeader
        step={0}
        back={`/events/${ready?.showtime.event.slug ?? closed?.slug ?? ""}`}
        backLabel={`Back to ${ready?.showtime.event.title ?? closed?.title ?? "the show"}`}
      />
      <main>
        {ready ? (
          <BookingView showtime={ready.showtime} layout={ready.layout} snapshot={ready.snapshot} />
        ) : (
          closed && (
            <div className="mx-auto grid w-[min(1240px,100%-32px)] justify-items-start gap-4 pt-16">
              <h1 className="font-cond text-[clamp(40px,6vw,64px)] leading-[.95] font-extrabold uppercase">
                {closed.reason === "cancelled" ? "This showtime was cancelled" : "This show has already started"}
              </h1>
              <p className="max-w-[52ch] text-muted-foreground">
                {closed.title} at {closed.venue}
                {closed.startsAt && `, ${when(closed.startsAt)}`}. Pick another showtime instead.
              </p>
              <Link href={closed.slug ? `/events/${closed.slug}` : "/events"} className={buttonVariants()}>
                Other showtimes
              </Link>
            </div>
          )
        )}
      </main>
    </>
  );
}
