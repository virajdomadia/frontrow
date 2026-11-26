import type { MetadataRoute } from "next";
import { api } from "@/lib/api";
import { SITE_URL } from "@/lib/site";

// The landing, the listings and one entry per event with upcoming showtimes. Regenerated hourly;
// if the api can't be reached (a CI build has none) it is the static pages alone until then.
export const revalidate = 3600;

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const pages: MetadataRoute.Sitemap = [
    { url: `${SITE_URL}/`, changeFrequency: "daily", priority: 1 },
    { url: `${SITE_URL}/events`, changeFrequency: "hourly", priority: 0.9 },
    { url: `${SITE_URL}/events?type=movie`, changeFrequency: "hourly", priority: 0.7 },
    { url: `${SITE_URL}/events?type=concert`, changeFrequency: "hourly", priority: 0.7 },
  ];
  try {
    const { events } = await api("/events", { revalidate: 3600, tags: ["events"] });
    return [
      ...pages,
      ...events.map((e) => ({ url: `${SITE_URL}/events/${e.slug}`, changeFrequency: "daily" as const, priority: 0.8 })),
    ];
  } catch {
    return pages;
  }
}
