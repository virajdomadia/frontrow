import type { NextConfig } from "next";

// Trailing slash stripped: `${API_URL}/:path*` would otherwise proxy to `//health`, which the api 404s.
const API_URL = (process.env.API_URL ?? "http://localhost:8000").replace(/\/$/, "");

const nextConfig: NextConfig = {
  // The browser only ever talks to this origin: `/api/*` is proxied to the FastAPI app, so the
  // session cookie is first-party and there is no CORS (05 §5).
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_URL}/:path*` }];
  },
};

export default nextConfig;
