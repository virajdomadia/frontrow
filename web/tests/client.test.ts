/** lib/next-path.ts — `?next=` after sign-in stays on this site (no open redirect). */
import assert from "node:assert/strict";
import { test } from "node:test";
import { safeNext } from "../src/lib/next-path.ts";

test("same-site paths pass through", () => {
  assert.equal(safeNext("/checkout/abc"), "/checkout/abc");
  assert.equal(safeNext("/book/1?x=2"), "/book/1?x=2");
});

test("anything that could leave the site falls back", () => {
  for (const bad of ["//evil.example", "/\\evil.example", "https://evil.example", "javascript:alert(1)", "", null, undefined])
    assert.equal(safeNext(bad, "/events"), "/events");
});
