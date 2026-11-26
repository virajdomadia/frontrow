import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { cache } from "react";
import { BookingView } from "@/components/booking/BookingView";
import { FlowHeader } from "@/components/booking/FlowHeader";
import { buttonVariants } from "@/components/ui/button";
import { api, ApiRequestError } from "@/lib/api";
import { when } from "@/lib/format";
import type { ShowDetail } from "@/lib/types";

// The detail is catalogue-fresh (60 s) and the layout immutable; the seat state is read per
// request with the viewer's cookie, so this page always renders dynamically. A show that has
// started or was cancelled is a 410 `show_closed`, whose details say enough to explain it.
type Closed = { reason: string; slug: string; title: string; cinema: string; startsAt: string };
type Loaded = { show: ShowDetail; closed: null } | { show: null; closed: Closed } | null;

function closedFrom(e: unknown): Closed | null {
  if (!(e instanceof ApiRequestError && e.status === 410)) return null;
  const d = (e.body.details ?? {}) as Record<string, unknown>;
  const str = (k: string) => (typeof d[k] === "string" ? (d[k] as string) : "");
  return { reason: str("reason"), slug: str("film_slug"), title: str("film_title"), cinema: str("cinema_name"), startsAt: str("starts_at") };
}

const getShow = cache(async (id: string): Promise<Loaded> => {
  try {
    const show = await api("/shows/{show_id}", { params: { show_id: id }, revalidate: 60, tags: [`show:${id}`] });
    if (show.status === "cancelled" || new Date(show.starts_at).getTime() <= Date.now())
      return {
        show: null,
        closed: {
          reason: show.status === "cancelled" ? "cancelled" : "started",
          slug: show.film.slug,
          title: show.film.title,
          cinema: show.cinema.name,
          startsAt: show.starts_at,
        },
      };
    return { show, closed: null };
  } catch (e) {
    if (e instanceof ApiRequestError && e.status === 404) return null;
    const closed = closedFrom(e);
    if (closed) return { show: null, closed };
    throw e;
  }
});

type Props = { params: Promise<{ showId: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const loaded = await getShow((await params).showId);
  if (!loaded) return { title: "Show not found", robots: { index: false } };
  if (loaded.closed) return { title: `Closed · ${loaded.closed.title}`, robots: { index: false } };
  const { show } = loaded;
  return {
    title: `Pick seats · ${show.film.title}`,
    description: `${show.film.title} at ${show.cinema.name}, ${when(show.starts_at)}. Pick your seats on the live map.`,
    robots: { index: false },
  };
}

/** C5 + C6 · Certificate notice, "How many seats?", then the live seat map with 10-minute holds. */
export default async function BookPage({ params }: Props) {
  const { showId } = await params;
  const loaded = await getShow(showId);
  if (!loaded) notFound();

  let closed = loaded.closed;
  let ready = null;
  if (loaded.show) {
    const show = loaded.show;
    try {
      const [layout, snapshot] = await Promise.all([
        api("/screens/{screen_id}/layout", { params: { screen_id: show.screen.id }, revalidate: 86_400, tags: [`screen:${show.screen.id}`] }),
        api("/shows/{show_id}/seats", { params: { show_id: show.id }, auth: true }),
      ]);
      ready = { show, layout, snapshot };
    } catch (e) {
      closed = closedFrom(e); // it started between the two reads
      if (!closed) throw e;
    }
  }
  const slug = ready?.show.film.slug ?? closed?.slug ?? "";

  return (
    <>
      <FlowHeader step={0} back={slug ? `/movies/${slug}/shows` : "/movies"} backLabel={`Back to ${ready?.show.film.title ?? closed?.title ?? "the film"} showtimes`} />
      <main>
        {ready ? (
          <BookingView show={ready.show} layout={ready.layout} snapshot={ready.snapshot} />
        ) : (
          closed && (
            <div className="mx-auto grid w-[min(1240px,100%-32px)] justify-items-start gap-4 pt-16">
              <h1 className="font-cond text-[clamp(40px,6vw,64px)] leading-[.95] font-extrabold uppercase">
                {closed.reason === "cancelled" ? "This show was cancelled" : "This show has already started"}
              </h1>
              <p className="max-w-[52ch] text-muted-foreground">
                {closed.title} at {closed.cinema}
                {closed.startsAt && `, ${when(closed.startsAt)}`}. Pick another time instead.
              </p>
              <Link href={closed.slug ? `/movies/${closed.slug}/shows` : "/movies"} className={buttonVariants()}>
                Other showtimes
              </Link>
            </div>
          )
        )}
      </main>
    </>
  );
}
