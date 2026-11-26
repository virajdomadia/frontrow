/**
 * Calendar exports for a booking: an RFC 5545 `.ics` body and a Google Calendar template link.
 * Pure — unit-tested in tests/calendar.test.ts.
 */

export type CalendarEntry = {
  uid: string;
  title: string;
  start: string; // ISO
  end: string; // ISO
  location: string;
  description: string;
  url: string;
};

/** 2026-11-26T14:00:00Z → 20261126T140000Z */
export function icsTime(iso: string): string {
  return new Date(iso).toISOString().replace(/[-:]/g, "").replace(/\.\d{3}/, "");
}

/** RFC 5545 text escaping: backslash, semicolon, comma, newline. */
export function icsText(s: string): string {
  return s.replace(/\\/g, "\\\\").replace(/;/g, "\\;").replace(/,/g, "\\,").replace(/\r?\n/g, "\\n");
}

export function ics(e: CalendarEntry, stamp = new Date().toISOString()): string {
  return [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//Frontrow//Tickets//EN",
    "CALSCALE:GREGORIAN",
    "METHOD:PUBLISH",
    "BEGIN:VEVENT",
    `UID:${e.uid}@frontrow`,
    `DTSTAMP:${icsTime(stamp)}`,
    `DTSTART:${icsTime(e.start)}`,
    `DTEND:${icsTime(e.end)}`,
    `SUMMARY:${icsText(e.title)}`,
    `LOCATION:${icsText(e.location)}`,
    `DESCRIPTION:${icsText(e.description)}`,
    `URL:${e.url}`,
    "BEGIN:VALARM",
    "TRIGGER:-PT2H",
    "ACTION:DISPLAY",
    `DESCRIPTION:${icsText(e.title)} starts in 2 hours`,
    "END:VALARM",
    "END:VEVENT",
    "END:VCALENDAR",
    "",
  ].join("\r\n");
}

export function googleCalendarUrl(e: CalendarEntry): string {
  const q = new URLSearchParams({
    action: "TEMPLATE",
    text: e.title,
    dates: `${icsTime(e.start)}/${icsTime(e.end)}`,
    location: e.location,
    details: `${e.description}\n${e.url}`,
  });
  return `https://calendar.google.com/calendar/render?${q}`;
}
