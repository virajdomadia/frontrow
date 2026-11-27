import type { NextConfig } from "next";

// Trailing slash stripped: `${API_URL}/:path*` would otherwise proxy to `//health`, which the api 404s.
const API_URL = (process.env.API_URL ?? "http://localhost:8000").replace(/\/$/, "");

/*
 * Security headers (05 §7; QA 2026-11-19, after Tripsmith's H4). Everything the browser may do
 * on this origin.
 *
 * `script-src` carries `'unsafe-inline'` rather than a nonce: Next's inline bootstrap
 * (`self.__next_f.push(…)`) and the event pages' JSON-LD are generated per page, and a nonce
 * means middleware on every request — every page dynamic, ISR gone. With no remote script
 * origin allowed at all, an injected `<script src>` still can't load anything; the JSON-LD is
 * escaped (`jsonLd()` in movies/[slug]).
 *
 * Everything is same-origin except Razorpay Checkout (F5): posters and venue photos are files in
 * public/ served through /_next/image, next/font self-hosts the fonts, and the browser reaches the
 * api only through the `/api/*` rewrite. Checkout loads Razorpay's script, which opens its own
 * iframe and talks to its own API — those origins and nothing else.
 *
 * HSTS is absent on purpose: Vercel sends it on every response already.
 */
const isDev = process.env.NODE_ENV === "development";
const RAZORPAY = "https://checkout.razorpay.com https://api.razorpay.com";

const csp = [
  "default-src 'self'",
  "base-uri 'self'",
  "object-src 'none'",
  "frame-ancestors 'none'",
  "form-action 'self'", // the movies search form (GET, same origin)
  `script-src 'self' 'unsafe-inline' https://checkout.razorpay.com${isDev ? " 'unsafe-eval'" : ""}`, // eval: React Refresh in dev
  `frame-src ${RAZORPAY}`,
  "style-src 'self' 'unsafe-inline'", // Tailwind + Next inject <style> elements
  "img-src 'self' data: https://*.razorpay.com",
  "font-src 'self'",
  `connect-src 'self' ${RAZORPAY} https://lumberjack.razorpay.com${isDev ? " ws:" : ""}`, // ws: the dev server's HMR socket
  // On Vercel only: `next start` on http://localhost would have its own requests upgraded.
  ...(process.env.VERCEL ? ["upgrade-insecure-requests"] : []),
].join("; ");

const securityHeaders = [
  { key: "Content-Security-Policy", value: csp },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "X-Frame-Options", value: "DENY" }, // for browsers older than `frame-ancestors`
  { key: "Cross-Origin-Opener-Policy", value: "same-origin" },
  // `payment` only for Razorpay's checkout frame (UPI / saved cards use the Payment Request API).
  { key: "Permissions-Policy", value: 'camera=(self), microphone=(), geolocation=(), payment=(self "https://api.razorpay.com"), usb=()' },
];

const nextConfig: NextConfig = {
  // The version banner tells an attacker which Next advisories to try; it buys nothing.
  poweredByHeader: false,
  // Vercel Hobby allows 5,000 image transformations a month; each source × width × quality is
  // one. Posters and venue photos are local files in public/, so keep the set closed: one
  // quality, a few widths, and each result cached for 30 days.
  images: {
    qualities: [75],
    deviceSizes: [640, 828, 1200, 1920],
    imageSizes: [256, 384],
    minimumCacheTTL: 60 * 60 * 24 * 30,
  },
  async headers() {
    // Everything except `/api/*`, which the rewrite hands to the api — the api answers with its
    // own headers, and two CSPs on one response are enforced as their intersection.
    return [{ source: "/((?!api/).*)", headers: securityHeaders }];
  },
  async redirects() {
    // Swagger UI through the rewrite would fetch `/openapi.json` from *this* origin (a 404) and
    // run under this origin's CSP. Send `/api/docs` to the api's own origin instead.
    return [{ source: "/api/docs", destination: `${API_URL}/docs`, permanent: false }];
  },
  // The browser only ever talks to this origin: `/api/*` is proxied to the FastAPI app, so the
  // session cookie is first-party and there is no CORS (05 §5).
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_URL}/:path*` }];
  },
};

export default nextConfig;
