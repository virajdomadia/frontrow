/**
 * Sign-in and sign-out happen in one component (DemoButtons, AccountLinks) while the header reads
 * the session in another. This browser event tells the header to update without waiting for the
 * URL to change — a demo sign-in on the home page lands on the home page.
 */
import type { Me } from "./types";

export const AUTH_EVENT = "frontrow:auth";

export function announceAuth(me: Me | null): void {
  window.dispatchEvent(new CustomEvent<Me | null>(AUTH_EVENT, { detail: me }));
}

/** True when navigating from `current` to `target` stays on the same page (path only). */
export function samePage(current: string, target: string): boolean {
  return current === target.split(/[?#]/)[0];
}
