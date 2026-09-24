import type { Metadata } from "next";
import Image from "next/image";
import { notFound } from "next/navigation";
import { cache } from "react";
import { FillBadge, TypeBadge } from "@/components/events/badges";
import { Showtimes, type ShowtimeDay } from "@/components/events/Showtimes";
import { SiteFooter, SiteHeader } from "@/components/site/SiteHeader";
import { api, ApiRequestError } from "@/lib/api";
import { dayKey, dayLabel, dayParts, duration, rupees, when } from "@/lib/format";
import { SITE_URL } from "@/lib/site";
import type { EventDetail } from "@/lib/types";

export const revalidate = 60;

const getEvent = cache(async (slug: string): Promise<EventDetail | null> => {
  try {
    return await api("/events/{slug}", { params: { slug }, revalidate: 60, tags: ["events", `event:${slug}`] });
  } catch (e) {
    if (e instanceof ApiRequestError && e.status === 404) return null;
    throw e;
  }
});

type Props = { params: Promise<{ slug: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const event = await getEvent((await params).slug);
  if (!event) return { title: "Show not found" };
  const lead = event.type === "movie" ? `${event.genre} · ${event.rating ?? "Unrated"}` : `${event.genre} live`;
  return {
    title: event.title,
    description: `${lead}. ${event.synopsis}`.slice(0, 160),
    alternates: { canonical: `/events/${event.slug}` },
    openGraph: { title: event.title, description: event.synopsis, images: [event.poster_url], type: "website" },
  };
}

export default async function EventPage({ params }: Props) {
  const event = await getEvent((await params).slug);
  if (!event) notFound();

  const now = new Date();
  const days = groupByDay(event, now);
  const venues = uniqueVenues(event);
  const facts = [
    event.type === "movie" ? event.rating : null,
    event.genre,
    event.type === "movie" ? duration(event.duration_min) : `${duration(event.duration_min)} set`,
    event.upcoming_count ? `${event.upcoming_count} upcoming ${event.upcoming_count === 1 ? "show" : "shows"}` : null,
  ].filter(Boolean);
  const castLabel = event.type === "movie" ? "Cast" : "Line-up";

  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: jsonLd(event) }} />
      <div className="relative isolate">
        {/* Backdrop: the poster, darkened into the plum ground. */}
        <div aria-hidden="true" className="absolute inset-x-0 top-0 -z-10 h-[420px] overflow-hidden">
          <Image src={event.poster_url} alt="" fill priority sizes="100vw" className="scale-110 object-cover opacity-70 blur-[2px]" />
          <div className="absolute inset-0 bg-[linear-gradient(rgba(42,11,30,.35),rgba(42,11,30,.7)_55%,var(--plum))]" />
        </div>
        <SiteHeader active={event.type === "movie" ? "movie" : "concert"} overlay />

        <main className="mx-auto w-[min(1240px,100%-32px)]">
          <section className="grid gap-6 pt-20 sm:grid-cols-[200px_1fr] sm:items-end sm:gap-8 sm:pt-28 lg:grid-cols-[260px_1fr] lg:pt-36">
            <div className="relative aspect-[2/3] w-40 overflow-hidden rounded-lg shadow-[0_24px_60px_rgba(0,0,0,.6)] sm:w-full">
              <Image src={event.poster_url} alt={`${event.title} poster`} fill priority sizes="(min-width: 1024px) 260px, 200px" className="object-cover" />
            </div>
            <div>
              <TypeBadge type={event.type} />
              <h1 className="mt-2 font-cond text-[clamp(48px,8vw,88px)] leading-[.9] font-extrabold text-balance uppercase">
                {event.title}
              </h1>
              <p className="mt-2.5 flex flex-wrap gap-x-2.5 text-[15px] text-muted-foreground">
                {facts.map((f, i) => (
                  <span key={i} className={i === 0 ? "font-semibold text-screen" : undefined}>
                    {i > 0 && <span aria-hidden="true" className="mr-2.5">·</span>}
                    {f}
                  </span>
                ))}
              </p>
              <p className="mt-3.5 max-w-[68ch] text-muted-foreground">{event.synopsis}</p>
              {event.cast_lineup.length > 0 && (
                <p className="mt-2.5 text-sm text-faint">
                  <b className="font-semibold text-muted-foreground">{castLabel}</b> {event.cast_lineup.join(" · ")}
                </p>
              )}
            </div>
          </section>

          <div className="mt-10 grid gap-10 lg:grid-cols-[1fr_320px]">
            <section aria-labelledby="showtimes-h">
              <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
                <h2 id="showtimes-h" className="font-cond text-[28px] leading-none font-bold uppercase">
                  Showtimes
                </h2>
                {event.next_showtime && (
                  <p className="flex items-center gap-2 text-sm text-muted-foreground">
                    Next: {when(event.next_showtime.starts_at, now)}
                    <FillBadge fill={event.next_showtime.fill} />
                  </p>
                )}
              </div>
              <Showtimes days={days} />
            </section>

            <aside className="grid content-start gap-5">
              <div className="rounded-card bg-paper px-5 py-[18px] text-ink">
                <h2 className="text-[11px] font-semibold tracking-[.14em] text-ink-3 uppercase">Good to know</h2>
                <ul className="mt-2 grid list-disc gap-1.5 pl-[18px] text-sm text-ink-2 marker:text-red-dark">
                  <li>
                    Seats are held for <b className="text-ink">10 minutes</b> once you tap them
                  </li>
                  <li>Tickets are QR codes — no printing</li>
                  <li>Convenience fee ₹30 per ticket</li>
                  <li>Up to 10 seats per order</li>
                  {event.from_price_paise != null && <li>Tickets from {rupees(event.from_price_paise)}</li>}
                </ul>
              </div>
              {venues.map((v) => (
                <figure key={v.id} className="m-0 overflow-hidden rounded-card bg-plum-2">
                  {v.photo_url && (
                    <div className="relative aspect-[16/9]">
                      <Image src={v.photo_url} alt={`Inside ${v.name}`} fill sizes="320px" className="object-cover" />
                    </div>
                  )}
                  <figcaption className="px-5 py-4">
                    <span className="text-[11px] font-semibold tracking-[.14em] text-faint uppercase">Venue</span>
                    <b className="mt-1 block font-cond text-xl leading-tight font-bold">{v.name}</b>
                    <p className="text-[13px] text-muted-foreground">{v.address}</p>
                  </figcaption>
                </figure>
              ))}
            </aside>
          </div>
        </main>
      </div>
      <SiteFooter />
    </>
  );
}

function groupByDay(event: EventDetail, now: Date): ShowtimeDay[] {
  const days = new Map<string, ShowtimeDay>();
  for (const s of event.showtimes) {
    const key = dayKey(s.starts_at);
    let day = days.get(key);
    if (!day) {
      const rel = dayLabel(s.starts_at, now);
      day = { key, ...dayParts(s.starts_at), relative: /^To/.test(rel) ? rel : undefined, venues: [] };
      days.set(key, day);
    }
    let venue = day.venues.find((v) => v.id === s.venue.id);
    if (!venue) {
      venue = { id: s.venue.id, name: s.venue.name, detail: `${s.venue.seat_count} seats · ${area(s.venue.address)}`, times: [] };
      day.venues.push(venue);
    }
    venue.times.push({
      id: s.id,
      startsAt: s.starts_at,
      min: s.price_min_paise,
      max: s.price_max_paise,
      fill: s.fill,
      seatsLeft: s.seats_left,
    });
  }
  return [...days.values()];
}

/** "100 Feet Road, Indiranagar, Bengaluru 560038" → "Indiranagar" */
function area(address: string) {
  const parts = address.split(",").map((p) => p.trim());
  return parts.length >= 3 ? parts[parts.length - 2] : parts[0];
}

function uniqueVenues(event: EventDetail) {
  const seen = new Map<string, EventDetail["showtimes"][number]["venue"]>();
  for (const s of event.showtimes) if (!seen.has(s.venue.id)) seen.set(s.venue.id, s.venue);
  return [...seen.values()];
}

/** One schema.org Event per upcoming showtime (06 §C / 04 §10). `<` is escaped for the script tag. */
function jsonLd(event: EventDetail) {
  const url = `${SITE_URL}/events/${event.slug}`;
  const image = new URL(event.poster_url, SITE_URL).toString();
  const items = event.showtimes.map((s) => ({
    "@context": "https://schema.org",
    "@type": event.type === "movie" ? "ScreeningEvent" : "MusicEvent",
    name: event.title,
    description: event.synopsis,
    image,
    url,
    startDate: s.starts_at,
    eventStatus: "https://schema.org/EventScheduled",
    eventAttendanceMode: "https://schema.org/OfflineEventAttendanceMode",
    location: {
      "@type": "Place",
      name: s.venue.name,
      address: { "@type": "PostalAddress", streetAddress: s.venue.address, addressLocality: "Bengaluru", addressCountry: "IN" },
    },
    offers: {
      "@type": "AggregateOffer",
      priceCurrency: "INR",
      lowPrice: s.price_min_paise / 100,
      highPrice: s.price_max_paise / 100,
      availability: s.fill === "sold_out" ? "https://schema.org/SoldOut" : "https://schema.org/InStock",
      url: `${SITE_URL}/book/${s.id}`,
    },
    ...(event.type === "movie"
      ? { workPresented: { "@type": "Movie", name: event.title, genre: event.genre, contentRating: event.rating ?? undefined } }
      : { performer: event.cast_lineup.map((name) => ({ "@type": "PerformingGroup", name })) }),
  }));
  return JSON.stringify(items).replace(/</g, "\\u003c");
}
