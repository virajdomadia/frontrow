/**
 * Display formatting. Every show is in Bengaluru, so dates and times always render in IST —
 * on the server and in the browser alike — whatever the viewer's own timezone.
 */

const TZ = "Asia/Kolkata";

const rupeeFmt = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 });
const timeFmt = new Intl.DateTimeFormat("en-IN", { timeZone: TZ, hour: "numeric", minute: "2-digit", hour12: true });
const weekdayFmt = new Intl.DateTimeFormat("en-GB", { timeZone: TZ, weekday: "short" });
const dayNumFmt = new Intl.DateTimeFormat("en-GB", { timeZone: TZ, day: "numeric" });
const monthFmt = new Intl.DateTimeFormat("en-GB", { timeZone: TZ, month: "short" });
const keyFmt = new Intl.DateTimeFormat("en-CA", { timeZone: TZ, year: "numeric", month: "2-digit", day: "2-digit" });

/** 22000 → "₹220" */
export function rupees(paise: number) {
  return `₹${rupeeFmt.format(Math.round(paise / 100))}`;
}

/** 22000, 56000 → "₹220–560" */
export function priceRange(minPaise: number, maxPaise: number) {
  if (minPaise === maxPaise) return rupees(minPaise);
  return `${rupees(minPaise)}–${rupeeFmt.format(Math.round(maxPaise / 100))}`;
}

/** "7:30 PM" */
export function showTime(iso: string) {
  return timeFmt.format(new Date(iso)).toUpperCase().replace(/\s+/g, " ");
}

/** IST calendar day, "2026-09-25" — the grouping key for showtimes. */
export function dayKey(iso: string | Date) {
  return keyFmt.format(typeof iso === "string" ? new Date(iso) : iso);
}

/** "Today" · "Tomorrow" · "Sat 27" — relative to `now`, in IST. */
export function dayLabel(iso: string, now: Date = new Date()) {
  const d = new Date(iso);
  const key = dayKey(d);
  if (key === dayKey(now)) return "Today";
  if (key === dayKey(new Date(now.getTime() + 86_400_000))) return "Tomorrow";
  return `${weekdayFmt.format(d)} ${dayNumFmt.format(d)}`;
}

/** Tab label for a day strip: { top: "Fri", bottom: "26 Sep" }. */
export function dayParts(iso: string) {
  const d = new Date(iso);
  return { weekday: weekdayFmt.format(d), date: `${dayNumFmt.format(d)} ${monthFmt.format(d)}` };
}

/** "Today 7:30 PM" */
export function when(iso: string, now?: Date) {
  return `${dayLabel(iso, now)} · ${showTime(iso)}`;
}

/** 134 → "2h 14m" */
export function duration(min: number) {
  const h = Math.floor(min / 60);
  const m = min % 60;
  return h ? `${h}h${m ? ` ${String(m).padStart(2, "0")}m` : ""}` : `${m}m`;
}
