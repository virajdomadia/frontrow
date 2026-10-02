import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { cache } from "react";
import { ArrowLeft } from "lucide-react";
import { BookingView } from "@/components/booking/BookingView";
import { Logo } from "@/components/site/Logo";
import { buttonVariants } from "@/components/ui/button";
import { api, ApiRequestError } from "@/lib/api";
import { when } from "@/lib/format";
import type { ShowtimeDetail } from "@/lib/types";
import { cn } from "@/lib/utils";

// The detail is catalog-fresh (60 s) and the layout immutable; the seat state is read per request
// with the viewer's cookie, so this page always renders dynamically.
const getShowtime = cache(async (id: string): Promise<ShowtimeDetail | null> => {
  try {
    return await api("/showtimes/{showtime_id}", { params: { showtime_id: id }, revalidate: 60, tags: [`showtime:${id}`] });
  } catch (e) {
    if (e instanceof ApiRequestError && e.status === 404) return null;
    throw e;
  }
});

type Props = { params: Promise<{ showtimeId: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const showtime = await getShowtime((await params).showtimeId);
  if (!showtime) return { title: "Show not found", robots: { index: false } };
  return {
    title: `Pick seats · ${showtime.event.title}`,
    description: `${showtime.event.title} at ${showtime.venue.name}, ${when(showtime.starts_at)}. Pick your seats on the live map.`,
    robots: { index: false },
  };
}

export default async function BookPage({ params }: Props) {
  const { showtimeId } = await params;
  const showtime = await getShowtime(showtimeId);
  if (!showtime) notFound();

  const closed =
    showtime.status === "cancelled"
      ? "This showtime was cancelled"
      : new Date(showtime.starts_at).getTime() <= Date.now()
        ? "This show has already started"
        : null;

  const [layout, snapshot] = closed
    ? [null, null]
    : await Promise.all([
        api("/venues/{venue_id}/layout", { params: { venue_id: showtime.venue.id }, revalidate: 86_400, tags: [`venue:${showtime.venue.id}`] }),
        api("/showtimes/{showtime_id}/seats", { params: { showtime_id: showtime.id }, auth: true }),
      ]);

  return (
    <>
      <BookHeader slug={showtime.event.slug} title={showtime.event.title} />
      <main>
        {layout && snapshot ? (
          <BookingView showtime={showtime} layout={layout} snapshot={snapshot} />
        ) : (
          <div className="mx-auto grid w-[min(1240px,100%-32px)] justify-items-start gap-4 pt-16">
            <h1 className="font-cond text-[clamp(40px,6vw,64px)] leading-[.95] font-extrabold uppercase">{closed}</h1>
            <p className="max-w-[52ch] text-muted-foreground">
              {showtime.event.title} at {showtime.venue.name}, {when(showtime.starts_at)}. Pick another showtime instead.
            </p>
            <Link href={`/events/${showtime.event.slug}`} className={buttonVariants()}>
              Other showtimes
            </Link>
          </div>
        )}
      </main>
    </>
  );
}

const STEPS = ["Seats", "Pay", "Ticket"];

function BookHeader({ slug, title }: { slug: string; title: string }) {
  return (
    <header className="border-b border-border">
      <nav aria-label="Booking" className="mx-auto flex w-[min(1440px,100%)] items-center justify-between gap-4 px-4 py-4 lg:px-10">
        <div className="flex items-center gap-2 sm:gap-5">
          <Link
            href={`/events/${slug}`}
            aria-label={`Back to ${title}`}
            className={cn(buttonVariants({ variant: "ghost", size: "sm" }), "px-2")}
          >
            <ArrowLeft />
          </Link>
          <Logo />
        </div>
        <ol className="flex list-none gap-4 p-0 font-cond text-[15px] font-semibold tracking-[.06em] text-faint uppercase sm:gap-6 sm:text-[17px]">
          {STEPS.map((s, i) => (
            <li
              key={s}
              aria-current={i === 0 ? "step" : undefined}
              className={cn("items-center aria-[current=step]:text-screen", i === 0 ? "flex" : "hidden sm:flex")}
            >
              {i === 0 && <span aria-hidden="true" className="mr-2 inline-block size-2 rounded-full bg-red" />}
              <span className="hidden sm:inline">{i + 1}&nbsp;</span>
              {s}
            </li>
          ))}
        </ol>
      </nav>
    </header>
  );
}
