import type { MetadataRoute } from "next";
import { SITE_URL } from "@/lib/site";

/** Everything public is crawlable; the seat map pages are `noindex` themselves (book/[id]). */
export default function robots(): MetadataRoute.Robots {
  return {
    rules: { userAgent: "*", allow: "/", disallow: ["/api/", "/book/", "/checkout/", "/tickets/", "/my-tickets", "/owner", "/staff"] },
    sitemap: `${SITE_URL}/sitemap.xml`,
  };
}
