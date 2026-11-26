"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { clockOffset } from "@/components/booking/holds";
import { send } from "@/lib/client";
import { fromSnapshot, mergeSnapshot, type SeatSnapshot, type SeatState } from "./core";

export const POLL_MS = 5_000;

/**
 * Live seat state for one show (04 §3): v1 polls `GET /shows/{id}/seats` every 5 s —
 * and at once when the tab comes back into view — and merges by version, so an older response
 * never overwrites a newer one. v2 swaps the poll for the SSE stream; the shape stays the same.
 */
export function useSeatState(showId: string, initial: SeatSnapshot) {
  const [state, setState] = useState<SeatState>(() => fromSnapshot(initial));
  const [snapshot, setSnapshot] = useState<SeatSnapshot>(initial);
  const [offset, setOffset] = useState(() => clockOffset(initial.server_time, Date.now()));
  const [stale, setStale] = useState(false);
  const inFlight = useRef<AbortController | null>(null);

  const refresh = useCallback(async () => {
    inFlight.current?.abort();
    const ctl = new AbortController();
    inFlight.current = ctl;
    const sent = Date.now();
    try {
      const snap = await send<SeatSnapshot>("GET", `/shows/${showId}/seats`, undefined, { signal: ctl.signal });
      // Half the round trip is the best guess for when the server stamped `server_time`.
      setOffset(clockOffset(snap.server_time, (sent + Date.now()) / 2));
      setState((prev) => mergeSnapshot(prev, snap));
      setSnapshot(snap);
      setStale(false);
      return snap;
    } catch (e) {
      if ((e as Error)?.name !== "AbortError") setStale(true);
      return null;
    }
  }, [showId]);

  useEffect(() => {
    let timer = window.setInterval(() => {
      if (document.visibilityState === "visible") void refresh();
    }, POLL_MS);
    const onVisible = () => {
      if (document.visibilityState !== "visible") return;
      void refresh();
      window.clearInterval(timer);
      timer = window.setInterval(() => void refresh(), POLL_MS);
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisible);
      inFlight.current?.abort();
    };
  }, [refresh]);

  /** Mark seats someone else just took (a 409) without waiting for the next poll. */
  const markHeld = useCallback((ids: string[]) => {
    setState((prev) => {
      const held = new Map(prev.held);
      for (const id of ids) if (!prev.sold.has(id)) held.set(id, new Date(Date.now() + 600_000).toISOString());
      return { ...prev, held };
    });
  }, []);

  return { state, snapshot, offset, stale, refresh, markHeld };
}
