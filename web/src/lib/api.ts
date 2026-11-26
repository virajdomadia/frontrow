import { headers as requestHeaders } from "next/headers";
import { errorFromResponse } from "./api-error";
import type { paths } from "./api-types";

/**
 * Typed server-side client for the api. Paths, responses and the error envelope come from
 * `api-types.ts`, generated from `api/openapi.json` (`pnpm gen:api`) — nothing here is typed by hand.
 * Browser code calls the same routes through the `/api/*` rewrite with plain `fetch`.
 */

export { ApiRequestError, errorFromResponse, type ApiErrorBody } from "./api-error";

// `new URL(path, BASE)` tolerates a trailing slash on API_URL; next.config.ts strips it for rewrites.
const BASE = process.env.API_URL ?? "http://localhost:8000";

/** Paths that have a GET operation in the contract. */
export type GetPath = {
  [P in keyof paths]: paths[P] extends { get: object } ? P : never;
}[keyof paths];

type JsonOf<R> = R extends { content: { "application/json": infer J } } ? J : never;
/** The 200 JSON body of `GET path`. */
export type GetResponse<P extends GetPath> = JsonOf<paths[P]["get"]["responses"][200]>;

export interface ApiInit {
  /** Values for `{name}` tokens in the path (`/events/{slug}`), URL-encoded. */
  params?: Record<string, string>;
  /** Cache tags for on-demand revalidation. */
  tags?: string[];
  revalidate?: number | false;
  /** Query string; an array appends one `k=v` per value; blanks and undefined are omitted. */
  searchParams?: Record<string, string | string[] | undefined>;
  /** Forward the viewer's `Cookie` header (session) and never cache — signed-in data only. */
  auth?: boolean;
  /**
   * An extra part for the data-cache key, for a response whose meaning changes while its URL
   * doesn't (`?date=weekend` after IST midnight). Sent as a header — Next keys cached fetches
   * on headers too — that the api ignores.
   */
  cacheKey?: string;
}

/** `/events/{slug}` + `{ slug: 'x' }` → `/events/x`. Throws rather than sending a literal `{slug}`. */
export function fillPath(path: string, params: Record<string, string> = {}) {
  return path.replace(/\{(\w+)\}/g, (_, name: string) => {
    const value = params[name];
    if (value === undefined) throw new Error(`Missing path param "${name}" for ${path}`);
    return encodeURIComponent(value);
  });
}

/** Server-side typed GET to the api; throws `ApiRequestError` on any non-2xx. */
export async function api<P extends GetPath>(path: P, init: ApiInit = {}): Promise<GetResponse<P>> {
  const url = new URL(fillPath(path, init.params), BASE);
  for (const [k, v] of Object.entries(init.searchParams ?? {}))
    for (const one of Array.isArray(v) ? v : [v]) if (one) url.searchParams.append(k, one);

  const headers = new Headers();
  if (init.cacheKey) headers.set("x-cache-key", init.cacheKey);
  let cache: RequestCache | undefined;
  if (init.auth) {
    // The raw header, not `cookies().toString()`: that re-encodes values and the api never
    // percent-decodes, so a token with `+ / =` would stop matching its row.
    const cookie = (await requestHeaders()).get("cookie");
    if (cookie) headers.set("cookie", cookie);
    cache = "no-store";
  }

  const res = await fetch(url, {
    headers,
    cache,
    next: { tags: init.tags, revalidate: init.revalidate },
  });
  if (!res.ok)
    throw errorFromResponse(res.status, res.statusText, await res.json().catch(() => undefined));
  return res.json() as Promise<GetResponse<P>>;
}
