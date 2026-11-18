/**
 * seat-map/core.ts — keyboard movement and seat names (QA 2026-11-19: arena sections 1–8 were
 * unreachable by keyboard; arena seat names repeated the tier). Run with `pnpm test`
 * (node:test, types stripped by Node itself — core.ts has no imports, so no bundler needed).
 */
import assert from "node:assert/strict";
import { test } from "node:test";
import {
  indexLayout,
  neighbour,
  seatLabel,
  sectionStart,
  sectionStep,
  sectionText,
  type Layout,
  type LayoutRow,
} from "../src/components/seat-map/core.ts";

const row = (section: string, label: string, n: number, y: number, x0 = 0): LayoutRow => ({
  label,
  seats: Array.from({ length: n }, (_, i) => ({ id: `${section}-${label}${i + 1}`, n: i + 1, x: x0 + i * 34, y })),
});

/** A floor block and three wedges side by side (positions only need to be plausible). */
const arena: Layout = {
  template: "arena",
  width: 1200,
  height: 800,
  stage: { label: "STAGE", x: 400, y: 0, w: 400 },
  tiers: [
    { key: "floor", label: "Floor" },
    { key: "gold", label: "Gold" },
  ],
  sections: [
    { key: "floor", label: "Floor", tier: "floor", shape: "rows", rows: [row("floor", "A", 5, 100, 400), row("floor", "B", 5, 134, 400)] },
    ...[1, 2, 3].map((k) => ({
      key: `s${k}`,
      label: `Section ${k}`,
      tier: "gold",
      shape: "wedge" as const,
      polygon: [
        [k * 300, 400],
        [k * 300 + 250, 400],
        [k * 300 + 250, 600],
        [k * 300, 600],
      ],
      rows: [row(`s${k}`, "A", 4, 420, k * 300), row(`s${k}`, "B", 5, 454, k * 300)],
    })),
  ],
};

const index = indexLayout(arena);
const all = () => true;

test("right off the end of a wedge row runs into the same row of the next wedge", () => {
  assert.equal(neighbour(index, "s1-A4", "right"), "s2-A1");
  assert.equal(neighbour(index, "s2-B1", "left"), "s1-B5");
  // The ring ends at the stage gap: the last wedge keeps its last seat.
  assert.equal(neighbour(index, "s3-A4", "right"), "s3-A4");
  assert.equal(neighbour(index, "s1-A1", "left"), "s1-A1");
});

test("rows-shaped sections still stop at their row ends", () => {
  assert.equal(neighbour(index, "floor-A5", "right"), "floor-A5");
  assert.equal(neighbour(index, "floor-A2", "down"), "floor-B2");
});

test("Page Down / Page Up reach every section, wrapping round", () => {
  const seen = new Set<string>();
  let id = "floor-A3";
  for (let i = 0; i < index.sections.length; i++) {
    id = sectionStep(index, id, 1, all);
    seen.add(index.byId.get(id)!.section);
  }
  assert.deepEqual([...seen].sort(), ["floor", "s1", "s2", "s3"]);
  assert.equal(index.byId.get(sectionStep(index, "floor-A3", -1, all))!.section, "s3");
});

test("a section's start seat is a free one near the middle of its front row", () => {
  assert.equal(sectionStart(index, "s2", all), "s2-A2");
  const sold = new Set(["s2-A1", "s2-A2", "s2-A3", "s2-A4"]);
  assert.equal(sectionStart(index, "s2", (id) => !sold.has(id)), "s2-B3");
  assert.equal(sectionStart(index, "nope", all), null);
});

test("seat names don't repeat a section the tier already names", () => {
  assert.equal(seatLabel("Floor", "A6", "Floor ₹3,500", "available"), "A6, Floor ₹3,500, available");
  assert.equal(seatLabel("Section 3", "B4", "Gold ₹2,500", "sold"), "Section 3, B4, Gold ₹2,500, sold");
  assert.equal(seatLabel(null, "G9", "Prime ₹320", "available"), "G9, Prime ₹320, available");
  assert.equal(sectionText("Floor", "Floor ₹3,500"), "Floor ₹3,500");
  assert.equal(sectionText("Section 2", undefined), "Section 2, not on sale");
});
