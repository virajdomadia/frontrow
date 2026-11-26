/**
 * Console-only formatting. Every venue is in Bengaluru, so organiser times are entered and shown
 * in IST whatever the browser's timezone; the api gets an ISO string with `+05:30`.
 */

const TZ = "Asia/Kolkata";

const fullFmt = new Intl.DateTimeFormat("en-GB", {
  timeZone: TZ,
  weekday: "short",
  day: "numeric",
  month: "short",
});
const timeFmt = new Intl.DateTimeFormat("en-IN", { timeZone: TZ, hour: "numeric", minute: "2-digit", hour12: true });
const partsFmt = new Intl.DateTimeFormat("en-CA", {
  timeZone: TZ,
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
});
const paidFmt = new Intl.DateTimeFormat("en-GB", {
  timeZone: TZ,
  day: "numeric",
  month: "short",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
});

/** "Sat 27 Nov · 7:30 PM" */
export function dateTime(iso: string) {
  const d = new Date(iso);
  return `${fullFmt.format(d)} · ${timeFmt.format(d).toUpperCase().replace(/\s+/g, " ")}`;
}

/** "27 Nov, 18:04" — for paid-at columns. */
export function stamp(iso: string | null | undefined) {
  return iso ? paidFmt.format(new Date(iso)) : "—";
}

/** IST `{ date: "2026-11-27", time: "19:30" }` for `<input type=date|time>` values. */
export function istInputs(iso: string | Date) {
  const parts = Object.fromEntries(partsFmt.formatToParts(new Date(iso)).map((p) => [p.type, p.value]));
  return { date: `${parts.year}-${parts.month}-${parts.day}`, time: `${parts.hour}:${parts.minute}` };
}

/** "2026-11-27" + "19:30" (IST) → "2026-11-27T19:30:00+05:30". */
export function istIso(date: string, time: string) {
  return `${date}T${time}:00+05:30`;
}

/** 22000 paise ↔ "220" rupees for price inputs. */
export function toRupeesInput(paise: number) {
  return String(Math.round(paise / 100));
}

export const TEMPLATE_LABEL: Record<"grid" | "stalls_balcony" | "arena", string> = {
  grid: "Cinema grid",
  stalls_balcony: "Stalls + balcony",
  arena: "Arena",
};
