import Link from "next/link";
import { EventCard } from "@/components/events/EventCard";
import { api } from "@/lib/api";
import type { EventCard as Card } from "@/lib/types";

/** S1 "Now showing" — the six soonest shows from `GET /home`. If the api is unreachable the
 *  landing still renders (the strip says so) and ISR retries within a minute. */
export async function Shows() {
  let shows: Card[] | null = null;
  try {
    shows = (await api("/home", { revalidate: 60, tags: ["events"] })).now_showing;
  } catch {
    shows = null;
  }
  const now = new Date();

  return (
    <section className="wrap shows" id="shows">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2>Now showing</h2>
          <p className="sub">Films and live shows across Bengaluru, one seat map each.</p>
        </div>
        <Link href="/events" className="text-[15px] text-muted-foreground hover:text-screen">
          All shows →
        </Link>
      </div>
      {shows && shows.length > 0 ? (
        <ul className="mt-7 grid list-none grid-cols-2 gap-3 p-0 sm:grid-cols-3 sm:gap-4 xl:grid-cols-6">
          {shows.map((e) => (
            <li key={e.id} className="grid">
              <EventCard event={e} now={now} showType={false} sizes="(min-width: 1280px) 16vw, (min-width: 640px) 33vw, 50vw" />
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-7 rounded-card bg-plum-2 px-5 py-4 text-muted-foreground">
          {shows ? "No shows scheduled right now — check back soon." : "The listings are taking a moment to load. "}
          {!shows && (
            <Link href="/events" className="text-screen">
              Browse all shows
            </Link>
          )}
        </p>
      )}
    </section>
  );
}
