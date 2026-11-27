/** lib/calendar.ts — the ticket page's "Add to calendar" (R6). */
import assert from "node:assert/strict";
import { test } from "node:test";
import { googleCalendarUrl, ics, icsText, icsTime } from "../src/lib/calendar.ts";

const entry = {
  uid: "order-1",
  title: "Yeh Prem Mol Liya",
  start: "2026-11-28T14:00:00.000Z",
  end: "2026-11-28T15:45:00.000Z",
  location: "Cadence Hall, 80 Feet Road, Koramangala",
  description: "Seats: D13; D14",
  url: "https://frontrow.example/tickets/order-1",
};

test("times are UTC basic format", () => {
  assert.equal(icsTime("2026-11-28T14:00:00.000Z"), "20261128T140000Z");
});

test("text is escaped per RFC 5545", () => {
  assert.equal(icsText("a,b;c\\d\ne"), "a\\,b\\;c\\\\d\\ne");
});

test("the .ics has one event with a 2-hour reminder, CRLF line ends", () => {
  const body = ics(entry, "2026-11-26T10:00:00Z");
  assert.ok(body.includes("\r\nDTSTART:20261128T140000Z\r\n"));
  assert.ok(body.includes("LOCATION:Cadence Hall\\, 80 Feet Road\\, Koramangala"));
  assert.ok(body.includes("TRIGGER:-PT2H"));
  assert.equal(body.match(/BEGIN:VEVENT/g)?.length, 1);
});

test("the Google link carries the same window", () => {
  const url = new URL(googleCalendarUrl(entry));
  assert.equal(url.searchParams.get("dates"), "20261128T140000Z/20261128T154500Z");
  assert.equal(url.searchParams.get("text"), "Yeh Prem Mol Liya");
});
