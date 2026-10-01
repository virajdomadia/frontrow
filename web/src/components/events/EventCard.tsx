import Image from "next/image";
import Link from "next/link";
import { duration, rupees, when } from "@/lib/format";
import type { EventCard as Card } from "@/lib/types";
import { TypeBadge } from "./badges";

/** Poster card for S1's strip and S2's grid. `now` keeps "Today"/"Tomorrow" consistent per render. */
export function EventCard({
  event,
  now,
  sizes = "(min-width: 1100px) 25vw, (min-width: 640px) 33vw, 50vw",
  priority = false,
  showType = true,
}: {
  event: Card;
  now: Date;
  sizes?: string;
  priority?: boolean;
  showType?: boolean;
}) {
  const next = event.next_showtime;
  const meta = [event.genre, event.type === "movie" ? event.rating : next?.venue_name, event.type === "movie" ? duration(event.duration_min) : null]
    .filter(Boolean)
    .join(" · ");
  return (
    <Link
      href={`/events/${event.slug}`}
      className="group grid grid-rows-[auto_1fr] overflow-hidden rounded-card bg-plum-2 text-screen no-underline transition-colors hover:bg-plum-3"
    >
      <div className="relative aspect-[2/3] overflow-hidden">
        <Image
          src={event.poster_url}
          alt=""
          fill
          sizes={sizes}
          priority={priority}
          className="object-cover transition-transform duration-500 ease-out group-hover:scale-[1.03] motion-reduce:transition-none"
        />
        {next?.fill === "filling" && (
          <span className="absolute top-2.5 right-2.5 rounded-chip bg-plum/85 px-2 py-1 font-cond text-sm font-bold tracking-[.06em] text-amber uppercase">
            Filling fast
          </span>
        )}
      </div>
      <div className="grid content-start gap-1.5 px-3.5 pt-3 pb-3.5">
        {showType && (
          <div>
            <TypeBadge type={event.type} />
          </div>
        )}
        <h3 className="font-cond text-[22px] leading-[.95] font-bold uppercase">{event.title}</h3>
        <p className="text-[13px] text-muted-foreground">{meta}</p>
        <div className="mt-auto flex flex-wrap items-baseline justify-between gap-x-2 pt-1">
          <b className="font-cond text-lg font-bold">
            {event.from_price_paise != null ? `from ${rupees(event.from_price_paise)}` : "—"}
          </b>
          {next && <span className="text-xs text-faint">{when(next.starts_at, now)}</span>}
        </div>
      </div>
    </Link>
  );
}
