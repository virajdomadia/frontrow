import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { BookButton } from "@/components/movies/BookButton";
import { CertBadge, FILL_LABEL } from "@/components/movies/badges";
import { SiteFooter, SiteHeader } from "@/components/site/SiteHeader";
import { api, ApiRequestError } from "@/lib/api";
import { dayParts, duration, priceRange, rupees, showTime } from "@/lib/format";
import type { Fill } from "@/lib/types";
import { cn } from "@/lib/utils";

type Props = {
  params: Promise<{ slug: string }>;
  searchParams: Promise<{ date?: string | string[]; language?: string | string[]; format?: string | string[] }>;
};

const one = (v: string | string[] | undefined) => (typeof v === "string" && v ? v : undefined);

async function load(slug: string, q: Awaited<Props["searchParams"]>) {
  const date = one(q.date);
  try {
    return await api("/films/{slug}/shows", {
      params: { slug },
      searchParams: {
        date: date && /^\d{4}-\d{2}-\d{2}$/.test(date) ? date : undefined,
        language: one(q.language),
        format: one(q.format),
      },
      revalidate: 30,
      tags: [`film:${slug}`],
      cacheKey: new Date().toISOString().slice(0, 13), // "today" moves at midnight
    });
  } catch (e) {
    if (e instanceof ApiRequestError && (e.status === 404 || e.status === 422)) return null;
    throw e;
  }
}

export async function generateMetadata({ params, searchParams }: Props): Promise<Metadata> {
  const data = await load((await params).slug, await searchParams);
  if (!data) return { title: "Showtimes", robots: { index: false } };
  return { title: `${data.film.title} showtimes in Bengaluru`, robots: { index: false } };
}

const TIME_STYLE: Record<Fill, string> = {
  available: "border-[#3E8E74] text-[#1F6F58] hover:bg-[#3E8E74] hover:text-white",
  filling: "border-amber text-amber hover:bg-amber hover:text-white",
  sold_out: "pointer-events-none border-ink/15 text-ink-3 line-through decoration-ink/40",
};

/** C4 · Showtimes: a date strip, then every cinema with its times coloured by availability. */
export default async function ShowtimesPage({ params, searchParams }: Props) {
  const { slug } = await params;
  const q = await searchParams;
  const data = await load(slug, q);
  if (!data) notFound();
  const { film } = data;
  const version = data.language && data.format ? `${data.language} · ${data.format}` : "";
  const link = (date: string) =>
    `/movies/${slug}/shows?${new URLSearchParams({ date, ...(data.language ? { language: data.language } : {}), ...(data.format ? { format: data.format } : {}) })}`;

  return (
    <>
      <SiteHeader active="movies" />
      <main id="main" className="mx-auto grid w-[min(1240px,100%-32px)] gap-6 py-8">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div className="grid gap-2">
            <Link href={`/movies/${slug}`} className="text-sm font-semibold text-muted-foreground no-underline hover:text-ink">
              ← {film.title}
            </Link>
            <h1 className="font-cond text-[clamp(38px,6vw,64px)] leading-[.92] font-extrabold uppercase">{film.title}</h1>
            <p className="flex flex-wrap items-center gap-2 text-[15px] text-muted-foreground">
              <CertBadge cert={film.cert} />
              {version && <b className="font-semibold text-ink">{version}</b>}
              <span aria-hidden="true">·</span>
              {duration(film.runtime_min)}
              <span aria-hidden="true">·</span>
              {film.genres.join(", ")}
            </p>
          </div>
          {data.versions.length > 1 && (
            <BookButton slug={slug} title={film.title} versions={data.versions} label="Change language / format" variant="outline" className="!px-4 !py-2 !text-base" />
          )}
        </div>

        {/* One row that scrolls sideways (no bar) and fades at the right edge, so it reads as more. */}
        <nav aria-label="Dates" className="-mx-4 overflow-x-auto px-4 [scrollbar-width:none] [mask-image:linear-gradient(90deg,#000_calc(100%-32px),transparent)] [&::-webkit-scrollbar]:hidden">
          <ol className="flex list-none gap-2 p-0 pr-8">
            {data.dates.map((d, i) => {
              const { weekday, date } = dayParts(`${d.date}T12:00:00+05:30`);
              const active = d.date === data.date;
              return (
                <li key={d.date}>
                  <Link
                    href={link(d.date)}
                    aria-current={active ? "date" : undefined}
                    aria-disabled={d.show_count === 0 || undefined}
                    className={cn(
                      "grid min-w-[76px] justify-items-center rounded-card border-2 px-3 py-2 whitespace-nowrap no-underline",
                      active ? "border-red bg-red text-white" : "border-ink/15 bg-plum-2 hover:border-ink/40",
                      d.show_count === 0 && !active && "pointer-events-none opacity-45",
                    )}
                  >
                    <span className="text-xs font-semibold tracking-[.08em] uppercase">{i === 0 ? "Today" : weekday}</span>
                    <b className="font-cond text-xl leading-tight">{date}</b>
                  </Link>
                </li>
              );
            })}
          </ol>
        </nav>

        <div className="flex flex-wrap gap-4 text-xs text-muted-foreground">
          <span className="flex items-center gap-1.5"><i className="inline-block size-3 rounded-sm border-2 border-[#3E8E74]" />{FILL_LABEL.available}</span>
          <span className="flex items-center gap-1.5"><i className="inline-block size-3 rounded-sm border-2 border-amber" />{FILL_LABEL.filling}</span>
          <span className="flex items-center gap-1.5"><i className="inline-block size-3 rounded-sm border-2 border-ink/20" />{FILL_LABEL.sold_out}</span>
        </div>

        {data.cinemas.length === 0 ? (
          <div className="fr-stub grid justify-items-start gap-3 p-6">
            <p className="font-semibold">No {version || ""} shows on this day.</p>
            <p className="text-sm text-muted-foreground">Pick another date above{data.versions.length > 1 ? ", or another language or format" : ""}.</p>
          </div>
        ) : (
          <ul className="grid list-none gap-3 p-0">
            {data.cinemas.map((c) => (
              <li key={c.id} className="grid gap-4 rounded-card border border-border bg-plum-2 p-5 lg:grid-cols-[300px_1fr]">
                <div>
                  <h2 className="font-cond text-2xl leading-none font-bold uppercase">{c.name}</h2>
                  <p className="mt-1 text-sm text-muted-foreground">{c.address}</p>
                  {c.facilities.length > 0 && <p className="mt-2 text-xs text-ink-3">{c.facilities.join(" · ")}</p>}
                </div>
                <div className="grid grid-cols-[repeat(auto-fill,minmax(128px,1fr))] content-start gap-2.5 lg:max-w-[720px]">
                  {c.shows.map((s) => {
                    const prices = s.tiers.map((t) => t.price_paise);
                    const label = `${showTime(s.starts_at)}, ${s.screen_name}, ${FILL_LABEL[s.fill]}${prices.length ? `, ${priceRange(Math.min(...prices), Math.max(...prices))}` : ""}`;
                    return s.fill === "sold_out" ? (
                      <span key={s.id} aria-label={label} className={cn("grid rounded-btn border-2 px-3.5 py-1.5 text-center", TIME_STYLE.sold_out)}>
                        <b className="font-cond text-lg leading-tight">{showTime(s.starts_at)}</b>
                        <span className="text-xs tracking-[.06em] uppercase">Sold out</span>
                      </span>
                    ) : (
                      <Link
                        key={s.id}
                        href={`/book/${s.id}`}
                        aria-label={label}
                        className={cn("grid rounded-btn border-2 bg-white/50 px-3.5 py-1.5 text-center no-underline transition-colors", TIME_STYLE[s.fill])}
                      >
                        <b className="font-cond text-lg leading-tight">{showTime(s.starts_at)}</b>
                        <span className="text-xs tracking-[.04em] uppercase">
                          {s.screen_name}
                          {s.format !== "2D" ? ` · ${s.format}` : ""}
                        </span>
                        {prices.length > 0 && <span className="text-xs font-semibold">from {rupees(Math.min(...prices))}</span>}
                      </Link>
                    );
                  })}
                </div>
              </li>
            ))}
          </ul>
        )}
        <p className="text-xs text-muted-foreground">Prices include taxes; a ₹30 convenience fee per ticket is added at checkout.</p>
      </main>
      <SiteFooter />
    </>
  );
}
