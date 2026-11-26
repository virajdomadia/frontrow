/** lib/filters.ts — unreadable params dropped; relative dates pinned to IST (QA 2026-11-19). */
import assert from "node:assert/strict";
import { test } from "node:test";
import { apiFilters, eventsHref, readFilters } from "../src/lib/filters.ts";

test("an unreadable value is dropped, not carried into links", () => {
  const { filters, rejected } = readFilters({ venue: "xyz", type: "concert", sort: "loudest" });
  assert.deepEqual(filters, { type: "concert" });
  assert.deepEqual(rejected, ["venue", "sort"]);
  assert.equal(eventsHref(filters, { date: "tomorrow" }), "/events?date=tomorrow&type=concert");
});

test("a repeated key takes its first non-empty value (the no-JS form)", () => {
  assert.equal(readFilters({ date: ["", "today"] }).filters.date, "today");
  assert.equal(readFilters({ date: ["2026-11-21", "today"] }).filters.date, "2026-11-21");
});

test("today / tomorrow become IST dates; weekend keys on the IST day", () => {
  // 00:05 IST on 20 Nov is still 19 Nov in UTC.
  const now = new Date("2026-11-19T18:35:00Z");
  assert.equal(apiFilters({ date: "today" }, now).filters.date, "2026-11-20");
  assert.equal(apiFilters({ date: "tomorrow" }, now).filters.date, "2026-11-21");
  const weekend = apiFilters({ date: "weekend", type: "movie" }, now);
  assert.deepEqual(weekend, { filters: { date: "weekend", type: "movie" }, day: "2026-11-20" });
});
