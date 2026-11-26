/** lib/auth-events.ts — after a demo sign-in, does the browser actually leave the page? */
import assert from "node:assert/strict";
import { test } from "node:test";
import { samePage } from "../src/lib/auth-events.ts";

test("the home page signing in to the home page stays put", () => {
  assert.equal(samePage("/", "/"), true);
});

test("query strings and hashes don't make it a different page", () => {
  assert.equal(samePage("/staff/businesses", "/staff/businesses?status=pending"), true);
  assert.equal(samePage("/my-tickets", "/my-tickets#upcoming"), true);
});

test("a different path is a real navigation", () => {
  assert.equal(samePage("/", "/owner"), false);
  assert.equal(samePage("/sign-in", "/"), false);
});
