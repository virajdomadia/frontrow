import type { MetadataRoute } from "next";
import { api } from "@/lib/api";
import { SITE_URL } from "@/lib/site";

// Home, the movie list and one entry per film. Regenerated hourly; if the api can't be reached
// (a CI build has none) it is the static pages alone until then.
export const revalidate = 3600;

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const pages: MetadataRoute.Sitemap = [
    { url: `${SITE_URL}/`, changeFrequency: "daily", priority: 1 },
    { url: `${SITE_URL}/movies`, changeFrequency: "hourly", priority: 0.9 },
    { url: `${SITE_URL}/business`, changeFrequency: "monthly", priority: 0.5 },
  ];
  try {
    const { films } = await api("/films", { revalidate: 3600, tags: ["films"] });
    return [...pages, ...films.map((f) => ({ url: `${SITE_URL}/movies/${f.slug}`, changeFrequency: "daily" as const, priority: 0.8 }))];
  } catch {
    return pages;
  }
}
