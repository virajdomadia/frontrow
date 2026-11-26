import { ApiRequestError, errorFromResponse } from "./api-error";

/**
 * Browser-side calls to the api through the same-origin `/api/*` rewrite, so the session
 * cookies are first-party and there is no CORS (05 §5). Mutations and live reads only — catalog
 * pages read on the server through `api.ts`.
 */
export async function send<T = unknown>(
  method: "GET" | "POST" | "PATCH" | "DELETE",
  path: string,
  body?: unknown,
  init: { signal?: AbortSignal; keepalive?: boolean } = {},
): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`/api${path}`, {
      method,
      headers: body === undefined ? undefined : { "content-type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
      credentials: "same-origin",
      cache: "no-store",
      signal: init.signal,
      keepalive: init.keepalive,
    });
  } catch (e) {
    if ((e as Error)?.name === "AbortError") throw e;
    throw new ApiRequestError(0, { code: "network", message: "You seem to be offline. Check your connection and try again." });
  }
  if (res.status === 204) return undefined as T;
  const json = await res.json().catch(() => undefined);
  if (!res.ok) throw errorFromResponse(res.status, res.statusText, json);
  return json as T;
}

/** `{ field: message }` from a validation error's details, for inline form errors. */
export function fieldErrors(e: unknown): Record<string, string> {
  if (!(e instanceof ApiRequestError)) return {};
  const fields = (e.body.details as { fields?: unknown } | undefined)?.fields;
  return fields && typeof fields === "object" ? (fields as Record<string, string>) : {};
}

/** A message fit to show a person. 5xx and network errors get a calm generic line. */
export function messageOf(e: unknown, fallback = "Something went wrong. Try again."): string {
  if (e instanceof ApiRequestError) {
    if (e.status === 0) return e.message;
    if (e.status >= 500 && e.body.code !== "unavailable" && e.body.code !== "payment_unavailable") return fallback;
    return e.body.message;
  }
  return fallback;
}

export { safeNext } from "./next-path";
