import type { NextConfig } from "next";

// Trailing slash stripped: `${API_URL}/:path*` would otherwise proxy to `//health`, which the api 404s.
const API_URL = (process.env.API_URL ?? "http://localhost:8000").replace(/\/$/, "");

const nextConfig: NextConfig = {
  // Vercel Hobby allows 5,000 image transformations a month; each source × width × quality is
  // one. Posters and venue photos are local files in public/, so keep the set closed: one
  // quality, a few widths, and each result cached for 30 days.
  images: {
    qualities: [75],
    deviceSizes: [640, 828, 1200, 1920],
    imageSizes: [256, 384],
    minimumCacheTTL: 60 * 60 * 24 * 30,
  },
  // The browser only ever talks to this origin: `/api/*` is proxied to the FastAPI app, so the
  // session cookie is first-party and there is no CORS (05 §5).
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_URL}/:path*` }];
  },
};

export default nextConfig;
