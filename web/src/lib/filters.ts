/** S2's filters live in the URL (`/events?date=&type=&genre=&venue=&sort=`); these build links. */

export const FILTER_KEYS = ["date", "type", "genre", "venue", "sort"] as const;
export type FilterKey = (typeof FILTER_KEYS)[number];
export type Filters = Partial<Record<FilterKey, string>>;

/**
 * What the api accepts for each key (`GET /events`, 06 §C). A value that fails here would only
 * come back as a 422, so it is dropped up front — and never copied into a link or offered as a
 * select option (QA 2026-11-19: `?venue=xyz` became "xyz (0)" and rode along on every chip).
 */
const VALID: Record<FilterKey, RegExp> = {
  date: /^(today|tomorrow|weekend|\d{4}-\d{2}-\d{2})$/,
  type: /^(movie|concert)$/,
  genre: /^.{1,40}$/,
  venue: /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i,
  sort: /^(soonest|price|title)$/,
};

/**
 * Known keys with a valid value. A repeated key takes its first non-empty value (the no-JS form
 * sends a blank date input beside the active preset). `rejected` lists keys whose value was
 * dropped as unreadable.
 */
export function readFilters(sp: Record<string, string | string[] | undefined>): { filters: Filters; rejected: FilterKey[] } {
  const filters: Filters = {};
  const rejected: FilterKey[] = [];
  for (const k of FILTER_KEYS) {
    const v = sp[k];
    const one = (Array.isArray(v) ? v : [v]).find((x) => x);
    if (!one) continue;
    if (VALID[k].test(one)) filters[k] = one;
    else rejected.push(k);
  }
  return { filters, rejected };
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

const istDay = new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Kolkata", year: "numeric", month: "2-digit", day: "2-digit" });

/**
 * The filters as sent to the api, with "today" / "tomorrow" pinned to IST dates. The word
 * "today" in a cache key means yesterday for a while after midnight (QA 2026-11-19); a date
 * doesn't. `day` is today's IST date — it keys the fetch for "weekend", which has no single date.
 */
export function apiFilters(f: Filters, now: Date): { filters: Filters; day: string } {
  const day = istDay.format(now);
  const date =
    f.date === "today" ? day : f.date === "tomorrow" ? istDay.format(new Date(now.getTime() + 86_400_000)) : f.date;
  return { filters: { ...f, date }, day };
}
