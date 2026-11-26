import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { notFound } from "next/navigation";
import { cache } from "react";
import { BookButton } from "@/components/movies/BookButton";
import { CERT_NOTE, CertBadge } from "@/components/movies/badges";
import { SiteFooter, SiteHeader } from "@/components/site/SiteHeader";
import { api, ApiRequestError } from "@/lib/api";
import { duration, rupees } from "@/lib/format";
import { SITE_URL } from "@/lib/site";

type Props = { params: Promise<{ slug: string }> };

const getFilm = cache(async (slug: string) => {
  try {
    return await api("/films/{slug}", { params: { slug }, revalidate: 60, tags: [`film:${slug}`] });
  } catch (e) {
    if (e instanceof ApiRequestError && e.status === 404) return null;
    throw e;
  }
});

const releaseFmt = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "long", year: "numeric", timeZone: "Asia/Kolkata" });

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const film = await getFilm((await params).slug);
  if (!film) return { title: "Film not found", robots: { index: false } };
  return {
    title: `${film.title} — tickets in Bengaluru`,
    description: film.synopsis.slice(0, 155),
    openGraph: { images: [{ url: film.poster_url }] },
  };
}

/** JSON-LD for the film, `<` escaped so a title can never close the script tag. */
function jsonLd(data: unknown) {
  return JSON.stringify(data).replace(/</g, "\\u003c");
}

/** C2 · Movie page: poster, banner, synopsis, cast and crew, certificate, runtime, trailer, Book. */
export default async function MoviePage({ params }: Props) {
  const film = await getFilm((await params).slug);
  if (!film) notFound();
  const soon = film.status === "coming_soon";
  const ended = film.status === "ended";
  const directors = film.cast_crew.filter((c) => c.role.toLowerCase() === "director");
  const cast = film.cast_crew.filter((c) => c.role.toLowerCase() !== "director");

  return (
    <>
      <SiteHeader active="movies" />
      <main>
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{
            __html: jsonLd({
              "@context": "https://schema.org",
              "@type": "Movie",
              name: film.title,
              image: `${SITE_URL}${film.poster_url}`,
              description: film.synopsis,
              duration: `PT${film.runtime_min}M`,
              genre: film.genres,
              director: directors.map((d) => ({ "@type": "Person", name: d.name })),
            }),
          }}
        />
        <section className="fr-banner -mt-[9px] pt-[9px] text-paper">
          <Image src={film.banner_url ?? film.poster_url} alt="" fill priority sizes="100vw" className="blur-[2px]" />
          <div className="mx-auto grid w-[min(1240px,100%-32px)] items-end gap-8 py-10 sm:grid-cols-[220px_1fr] lg:py-14">
            <div className="relative hidden aspect-[2/3] overflow-hidden rounded-card shadow-[0_20px_50px_rgb(0_0_0_/_.45)] sm:block">
              <Image src={film.poster_url} alt={`${film.title} poster`} fill sizes="220px" className="object-cover" priority />
            </div>
            <div className="grid gap-4">
              <h1 className="font-cond text-[clamp(48px,8vw,96px)] leading-[.9] font-extrabold text-white uppercase">{film.title}</h1>
              <p className="flex flex-wrap items-center gap-x-3 gap-y-2 text-[15px] text-paper/90">
                <CertBadge cert={film.cert} className="text-paper" />
                <span>{duration(film.runtime_min)}</span>
                <span aria-hidden="true">·</span>
                <span>{film.genres.join(", ")}</span>
                <span aria-hidden="true">·</span>
                <span>{soon ? `Releases ${releaseFmt.format(new Date(film.release_date))}` : `Released ${releaseFmt.format(new Date(film.release_date))}`}</span>
              </p>
              <div className="flex flex-wrap gap-2">
                {film.languages.map((l) => (
                  <span key={l} className="rounded-chip bg-paper/15 px-2.5 py-1 text-sm font-medium">
                    {l}
                  </span>
                ))}
                {film.formats.map((f) => (
                  <span key={f} className="rounded-chip border border-paper/40 px-2.5 py-1 font-cond text-sm font-bold tracking-[.06em]">
                    {f}
                  </span>
                ))}
              </div>
              <div className="flex flex-wrap items-center gap-4 pt-2">
                {film.show_count > 0 ? (
                  <>
                    <BookButton slug={film.slug} title={film.title} versions={film.versions} />
                    <span className="text-sm text-paper/85">
                      {film.show_count} shows this fortnight{film.from_price_paise ? ` · from ${rupees(film.from_price_paise)}` : ""}
                    </span>
                  </>
                ) : (
                  <p className="rounded-btn bg-paper/15 px-4 py-3 font-medium">
                    {soon
                      ? `Bookings open closer to release on ${releaseFmt.format(new Date(film.release_date))}.`
                      : ended
                        ? "This film has finished its run."
                        : "No shows on sale right now — cinemas are adding more."}
                  </p>
                )}
                {film.trailer_url && (
                  <a href={film.trailer_url} target="_blank" rel="noopener noreferrer" className="font-semibold text-paper underline underline-offset-4">
                    Watch the trailer ↗
                  </a>
                )}
              </div>
            </div>
          </div>
        </section>

        <div className="mx-auto grid w-[min(1240px,100%-32px)] gap-10 py-10 lg:grid-cols-[1.3fr_1fr]">
          <section aria-labelledby="about" className="grid content-start gap-3">
            <h2 id="about" className="font-cond text-3xl font-extrabold uppercase">
              About the movie
            </h2>
            <p className="max-w-[65ch] text-[17px] leading-relaxed">{film.synopsis}</p>
            <p className="mt-2 flex items-center gap-2 text-sm text-muted-foreground">
              <CertBadge cert={film.cert} /> {CERT_NOTE[film.cert]}
            </p>
          </section>
          <section aria-labelledby="cast" className="grid content-start gap-4">
            <h2 id="cast" className="font-cond text-3xl font-extrabold uppercase">
              Cast &amp; crew
            </h2>
            <ul className="grid list-none grid-cols-2 gap-3 p-0 sm:grid-cols-3">
              {[...directors, ...cast].map((p) => (
                <li key={`${p.name}-${p.role}`} className="flex items-center gap-3">
                  <span aria-hidden="true" className="grid size-11 shrink-0 place-items-center rounded-full bg-plum-3 font-cond text-lg font-bold text-ink-2">
                    {p.name
                      .split(" ")
                      .map((w) => w[0])
                      .slice(0, 2)
                      .join("")}
                  </span>
                  <span className="grid leading-tight">
                    <b className="text-[15px] font-semibold">{p.name}</b>
                    <span className="text-xs text-muted-foreground">{p.role}</span>
                  </span>
                </li>
              ))}
            </ul>
          </section>
        </div>
        <p className="mx-auto w-[min(1240px,100%-32px)] text-sm text-muted-foreground">
          <Link href="/movies" className="underline underline-offset-4">
            ← All movies
          </Link>
        </p>
      </main>
      <SiteFooter />
    </>
  );
}
