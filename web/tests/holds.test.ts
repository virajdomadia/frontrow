/** components/booking/holds.ts — the client's side of the hold engine (F2). */
import assert from "node:assert/strict";
import { test } from "node:test";
import { clockOffset, mmss, reconcile, remainingMs, takenNames } from "../src/components/booking/holds.ts";

test("mm:ss never shows a negative or fractional second", () => {
  assert.equal(mmss(600_000), "10:00");
  assert.equal(mmss(59_001), "01:00"); // ceil: 59.001 s left still reads 1:00
  assert.equal(mmss(1), "00:01");
  assert.equal(mmss(0), "00:00");
  assert.equal(mmss(-5_000), "00:00");
});

test("remaining time uses the server clock, not the device's", () => {
  // Server says it is 12:00:00 when the device thinks 12:00:30 → offset −30 s.
  const offset = clockOffset("2026-11-26T12:00:00Z", Date.parse("2026-11-26T12:00:30Z"));
  assert.equal(offset, -30_000);
  const deviceNow = Date.parse("2026-11-26T12:00:30Z");
  assert.equal(remainingMs("2026-11-26T12:10:00Z", deviceNow, offset), 600_000);
  assert.equal(remainingMs(null, deviceNow, offset), 0);
});

test("a poll adopts holds from another tab and drops lapsed ones", () => {
  const r = reconcile(["a", "b"], ["b", "c"], new Set(), new Set());
  assert.deepEqual(r.selected, ["b", "c"]);
  assert.deepEqual(r.lost, ["a"]);
});

test("in-flight taps win over a poll that predates them", () => {
  // "a" is being added (server doesn't know yet); "b" is being released (server still has it).
  const r = reconcile(["a", "b"], ["b"], new Set(["a"]), new Set(["b"]));
  assert.deepEqual(r.selected, ["a"]);
  assert.deepEqual(r.lost, []);
});

test("a 409 names the taken seats in hall order", () => {
  const names = new Map([
    ["s1", "F6"],
    ["s2", "F7"],
  ]);
  assert.equal(takenNames(["s2"], (id) => names.get(id) ?? id), "F7 was just taken");
  assert.equal(takenNames(["s1", "s2"], (id) => names.get(id) ?? id), "F6 and F7 were just taken");
  assert.equal(takenNames(["s1", "s2", "x"], (id) => names.get(id) ?? id), "F6, F7 and x were just taken");
});
