import Image from "next/image";
import Link from "next/link";
import { duration, rupees } from "@/lib/format";
import type { FilmCard as Film } from "@/lib/types";
import { CertBadge } from "./badges";

const releaseFmt = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", timeZone: "Asia/Kolkata" });

/** A poster card: Now showing (with the cheapest seat) or Coming soon (with the release date). */
export function FilmCard({ film, priority = false }: { film: Film; priority?: boolean }) {
  const soon = film.status === "coming_soon";
  return (
    <Link href={`/movies/${film.slug}`} className="group grid content-start gap-2.5 no-underline">
      <div className="relative aspect-[2/3] overflow-hidden rounded-card bg-plum-3 shadow-[0_10px_24px_rgb(42_11_30_/_.16)]">
        <Image
          src={film.poster_url}
          alt=""
          fill
          sizes="(min-width: 1024px) 220px, (min-width: 640px) 30vw, 45vw"
          priority={priority}
          className="object-cover transition-transform duration-500 group-hover:scale-[1.04] motion-reduce:transition-none"
        />
        <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-[rgb(42_11_30_/_.85)] to-transparent px-3 pt-10 pb-2.5 text-paper">
          <span className="font-cond text-sm font-semibold tracking-[.08em] uppercase">
            {soon ? `Releases ${releaseFmt.format(new Date(film.release_date))}` : film.from_price_paise ? `From ${rupees(film.from_price_paise)}` : "Now showing"}
          </span>
        </div>
      </div>
      <div className="grid gap-1">
        <h3 className="font-cond text-[22px] leading-[1] font-bold uppercase group-hover:text-red-dark">{film.title}</h3>
        <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[13px] text-muted-foreground">
          <CertBadge cert={film.cert} className="h-[18px] min-w-[22px] text-xs" />
          <span>{film.genres.join(" · ")}</span>
          <span aria-hidden="true">·</span>
          <span>{duration(film.runtime_min)}</span>
        </p>
        <p className="text-[13px] text-ink-3">{film.languages.join(", ")}</p>
      </div>
    </Link>
  );
}
