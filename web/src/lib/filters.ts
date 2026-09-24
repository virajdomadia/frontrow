/** S2's filters live in the URL (`/events?date=&type=&genre=&venue=&sort=`); these build links. */

export const FILTER_KEYS = ["date", "type", "genre", "venue", "sort"] as const;
export type FilterKey = (typeof FILTER_KEYS)[number];
export type Filters = Partial<Record<FilterKey, string>>;

/** Keep only known keys with a single non-empty string value. */
export function readFilters(sp: Record<string, string | string[] | undefined>): Filters {
  const out: Filters = {};
  for (const k of FILTER_KEYS) {
    const v = sp[k];
    const one = Array.isArray(v) ? v[0] : v;
    if (one) out[k] = one;
  }
  return out;
}

/** `/events?…` with `patch` applied; `undefined` removes a key; `sort=soonest` is the default. */
export function eventsHref(current: Filters, patch: Filters = {}) {
  const next = { ...current, ...patch };
  const qs = new URLSearchParams();
  for (const k of FILTER_KEYS) {
    const v = next[k];
    if (v && !(k === "sort" && v === "soonest")) qs.set(k, v);
  }
  const s = qs.toString();
  return s ? `/events?${s}` : "/events";
}

export const DATE_PRESETS = [
  { value: "today", label: "Today" },
  { value: "tomorrow", label: "Tomorrow" },
  { value: "weekend", label: "This weekend" },
] as const;
