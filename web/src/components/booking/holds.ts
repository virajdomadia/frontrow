/**
 * The client's side of the hold engine (F2) — pure functions, no React or DOM, unit-tested.
 *
 * The map's selection is the server's `mine` reconciled with taps still in flight: a poll that
 * was sent before a tap landed must not undo it, and a seat the server no longer holds for us
 * (expired, or released from another tab) drops out.
 */

/** ms → "mm:ss", rounded up so the clock reads 00:00 only when time is truly up. */
export function mmss(ms: number): string {
  const s = Math.max(0, Math.ceil(ms / 1000));
  return `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
}

/** Server time − device time, from a snapshot's `server_time` (04 §10 clock skew). */
export function clockOffset(serverTime: string, deviceNow: number): number {
  return Date.parse(serverTime) - deviceNow;
}

/** Milliseconds until `expiresAt` on the server's clock. */
export function remainingMs(expiresAt: string | null | undefined, deviceNow: number, offset: number): number {
  if (!expiresAt) return 0;
  return Math.max(0, Date.parse(expiresAt) - (deviceNow + offset));
}

/**
 * Merge a poll's `mine` into the local selection.
 * - `adding`: tapped, hold request not answered yet → keep.
 * - `removing`: released, request not answered yet → keep out.
 * - otherwise the server is the truth: adopt its seats (another tab of ours), drop the rest.
 */
export function reconcile(
  selected: string[],
  serverMine: string[],
  adding: ReadonlySet<string>,
  removing: ReadonlySet<string>,
): { selected: string[]; lost: string[] } {
  const server = new Set(serverMine);
  const kept = selected.filter((id) => adding.has(id) || (server.has(id) && !removing.has(id)));
  const lost = selected.filter((id) => !kept.includes(id) && !removing.has(id));
  const adopted = serverMine.filter((id) => !kept.includes(id) && !removing.has(id));
  return { selected: [...kept, ...adopted], lost };
}

/** "F7 was just taken" · "F6 and F7 were just taken" · "A1, A2 and A3 were just taken". */
export function takenNames(ids: string[], name: (id: string) => string): string {
  const names = ids.map(name);
  const list = names.length < 2 ? names.join("") : `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}`;
  return `${list} ${names.length === 1 ? "was" : "were"} just taken`;
}

/**
 * "How many seats?" picking (R5): tapping a seat takes `count` seats together in that row —
 * the tapped seat, then free seats to its right, then to its left — stopping at anything that
 * isn't free. Returns fewer than `count` when the run is shorter; the rest are tapped one by one.
 * `row` is the row's seat ids in seat-number order.
 */
export function pickTogether(row: readonly string[], start: string, count: number, isFree: (id: string) => boolean): string[] {
  const at = row.indexOf(start);
  if (at < 0 || count < 1 || !isFree(start)) return [];
  const out = [start];
  for (let i = at + 1; i < row.length && out.length < count && isFree(row[i]); i++) out.push(row[i]);
  for (let i = at - 1; i >= 0 && out.length < count && isFree(row[i]); i--) out.unshift(row[i]);
  return out;
}
