import type { Metadata } from "next";
import { FilmCard } from "@/components/movies/FilmCard";
import { SearchBox } from "@/components/movies/SearchBox";
import { SiteFooter, SiteHeader } from "@/components/site/SiteHeader";
import { api } from "@/lib/api";

type Props = { searchParams: Promise<{ q?: string | string[] }> };

export async function generateMetadata({ searchParams }: Props): Promise<Metadata> {
  const q = (await searchParams).q;
  return typeof q === "string" && q.trim()
    ? { title: `“${q.trim()}” · Movies`, robots: { index: false } }
    : { title: "Movies in Bengaluru", description: "Every film on Frontrow: now showing and coming soon." };
}

/** Search results, or every film when there's no query (now showing first, then coming soon). */
export default async function MoviesPage({ searchParams }: Props) {
  const raw = (await searchParams).q;
  const q = typeof raw === "string" ? raw.trim().slice(0, 60) : "";
  const data = await api("/films", { searchParams: { q: q || undefined }, revalidate: 60, tags: ["films"] });
  const showing = data.films.filter((f) => f.status === "now_showing");
  const soon = data.films.filter((f) => f.status === "coming_soon");
  return (
    <>
      <SiteHeader active="movies" />
      <main id="main" className="mx-auto grid w-[min(1240px,100%-32px)] gap-8 py-8">
        <div className="grid gap-4">
          <h1 className="font-cond text-[clamp(40px,6vw,72px)] leading-[.92] font-extrabold uppercase">
            {q ? `Results for “${q}”` : "Movies in Bengaluru"}
          </h1>
          <SearchBox defaultValue={q} className="max-w-[560px]" />
          {q && (
            <p className="text-sm text-muted-foreground" aria-live="polite">
              {data.films.length === 0 ? "No films match — try a shorter word, or a genre like “thriller”." : `${data.films.length} ${data.films.length === 1 ? "film" : "films"}`}
            </p>
          )}
        </div>
        {showing.length > 0 && (
          <section aria-labelledby="showing" className="grid gap-5">
            <h2 id="showing" className="font-cond text-3xl font-extrabold uppercase">
              Now showing
            </h2>
            <div className="grid grid-cols-2 gap-x-5 gap-y-8 sm:grid-cols-3 lg:grid-cols-5">
              {showing.map((f, i) => (
                <FilmCard key={f.id} film={f} priority={i < 5} />
              ))}
            </div>
          </section>
        )}
        {soon.length > 0 && (
          <section aria-labelledby="soon" className="grid gap-5">
            <h2 id="soon" className="font-cond text-3xl font-extrabold uppercase">
              Coming soon
            </h2>
            <div className="grid grid-cols-2 gap-x-5 gap-y-8 sm:grid-cols-3 lg:grid-cols-5">
              {soon.map((f) => (
                <FilmCard key={f.id} film={f} />
              ))}
            </div>
          </section>
        )}
      </main>
      <SiteFooter />
    </>
  );
}
