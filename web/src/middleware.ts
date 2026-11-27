import { NextResponse, type NextRequest } from "next/server";

/**
 * The browser reaches the api only through the `/api/*` rewrite, so the api sees this proxy's
 * address, not the visitor's. Pass the visitor's address on (Vercel sets `x-real-ip` at its edge;
 * a client can't), proven with PROXY_SECRET so nobody calling the api directly can forge it. The
 * api keys its per-network limits on it (seat holds, sign-in codes).
 */
export function middleware(request: NextRequest) {
  const secret = process.env.PROXY_SECRET;
  const ip = request.headers.get("x-real-ip");
  if (!secret || !ip) return NextResponse.next();
  const headers = new Headers(request.headers);
  headers.set("x-frontrow-client-ip", ip);
  headers.set("x-frontrow-proxy", secret);
  return NextResponse.next({ request: { headers } });
}

export const config = { matcher: "/api/:path*" };
