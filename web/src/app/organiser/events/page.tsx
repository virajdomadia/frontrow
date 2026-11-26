import Image from "next/image";
import Link from "next/link";
import { Empty, PageHead, StatusBadge } from "@/components/organiser/ui";
import { buttonVariants } from "@/components/ui/button";
import { api } from "@/lib/api";
import { duration } from "@/lib/format";

export const metadata = { title: "Events" };

type Props = { searchParams: Promise<{ saved?: string }> };

/** S11 · every event, live or draft, with what's scheduled and sold. */
export default async function EventsPage({ searchParams }: Props) {
  const saved = (await searchParams).saved;
  const events = await api("/organiser/events", { auth: true });
  const justSaved = saved ? events.find((e) => e.slug === saved) : undefined;
  return (
    <>
      <PageHead
        title="Events"
        sub={events.length ? `${events.filter((e) => e.status === "live").length} live · ${events.filter((e) => e.status === "draft").length} draft` : undefined}
        action={
          <Link href="/organiser/events/new" className={buttonVariants({ size: "sm" })}>
            New event
          </Link>
        }
      />
      {justSaved && (
        <p role="status" className="mb-5 rounded-card border border-classic/40 bg-classic/10 px-4 py-3 text-sm">
          Saved “{justSaved.title}”.{" "}
          {justSaved.upcoming_showtimes === 0 && (
            <Link href={`/organiser/showtimes/new?event_id=${justSaved.id}`} className="font-semibold underline underline-offset-4">
              Add a showtime to put it on sale
            </Link>
          )}
        </p>
      )}
      {events.length ? (
        <ul className="grid list-none gap-2.5 p-0">
          {events.map((e) => (
            <li key={e.id} className="grid grid-cols-[56px_1fr] items-center gap-4 rounded-card bg-plum-2 p-3 sm:grid-cols-[56px_1fr_auto]">
              <div className="relative aspect-[2/3] overflow-hidden rounded-btn bg-plum-3">
                <Image src={e.poster_url} alt="" fill sizes="56px" className="object-cover" />
              </div>
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <b className="font-cond text-[22px] leading-tight font-bold">{e.title}</b>
                  <StatusBadge status={e.status} />
                </div>
                <p className="text-sm text-muted-foreground">
                  {e.type === "movie" ? "Movie" : "Concert"} · {e.genre}
                  {e.rating ? ` · ${e.rating}` : ""} · {duration(e.duration_min)}
                </p>
                <p className="text-xs text-faint">
                  {e.upcoming_showtimes} upcoming {e.upcoming_showtimes === 1 ? "showtime" : "showtimes"} · {e.tickets_sold.toLocaleString("en-IN")} tickets sold
                </p>
              </div>
              <div className="col-span-2 flex flex-wrap gap-2 sm:col-span-1 sm:justify-end">
                <Link href={`/organiser/events/${e.id}`} className={buttonVariants({ variant: "outline", size: "sm" })}>
                  Edit
                </Link>
                <Link href={`/organiser/showtimes?event_id=${e.id}`} className={buttonVariants({ variant: "ghost", size: "sm" })}>
                  Showtimes
                </Link>
                {e.status === "live" && (
                  <Link href={`/events/${e.slug}`} className={buttonVariants({ variant: "ghost", size: "sm" })}>
                    View page ↗
                  </Link>
                )}
              </div>
            </li>
          ))}
        </ul>
      ) : (
        <Empty
          title="No events yet"
          body="An event is the film or concert itself — title, poster, synopsis. Create one, then schedule showtimes at your venues."
          href="/organiser/events/new"
          cta="Create your first event"
        />
      )}
    </>
  );
}
