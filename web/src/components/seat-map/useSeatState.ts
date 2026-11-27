"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { clockOffset } from "@/components/booking/holds";
import { send } from "@/lib/client";
import { fromSnapshot, mergeSnapshot, type SeatSnapshot, type SeatState } from "./core";

export const POLL_MS = 5_000;
/** Stream errors in a row (without one good event) before the map falls back to polling. */
const STREAM_FAILS = 2;

/**
 * Live seat state for one show (04 §3, L1). The API pushes a `snapshot` over SSE
 * (`/shows/{id}/stream`) on every hold, release, sale or lapse, and nothing while the hall is
 * quiet. If the stream can't be had (no EventSource, the API answers 503, or it fails twice in
 * a row), the hook polls `GET /shows/{id}/seats` every 5 s instead. Either way snapshots merge by
 * version, so an older one never overwrites a newer one. A hidden tab closes the stream (and
 * stops polling) and catches up the moment it's visible again.
 */
export function useSeatState(showId: string, initial: SeatSnapshot) {
  const [state, setState] = useState<SeatState>(() => fromSnapshot(initial));
  const [snapshot, setSnapshot] = useState<SeatSnapshot>(initial);
  const [offset, setOffset] = useState(() => clockOffset(initial.server_time, Date.now()));
  const [stale, setStale] = useState(false);
  const [polling, setPolling] = useState(false);
  const inFlight = useRef<AbortController | null>(null);
  const latest = useRef(initial.v);

  const take = useCallback((snap: SeatSnapshot, sentAt: number) => {
    // Stream and poll can race (tab comes back): an older answer must not undo a newer one.
    // Equal is fine: a lapse changes the holds without bumping the version.
    if (snap.v < latest.current) return;
    latest.current = snap.v;
    // Half the round trip is the best guess for when the server stamped `server_time`.
    setOffset(clockOffset(snap.server_time, (sentAt + Date.now()) / 2));
    setState((prev) => mergeSnapshot(prev, snap));
    setSnapshot(snap);
    setStale(false);
  }, []);

  const refresh = useCallback(async () => {
    inFlight.current?.abort();
    const ctl = new AbortController();
    inFlight.current = ctl;
    const sent = Date.now();
    try {
      const snap = await send<SeatSnapshot>("GET", `/shows/${showId}/seats`, undefined, { signal: ctl.signal });
      take(snap, sent);
      return snap;
    } catch (e) {
      if ((e as Error)?.name !== "AbortError") setStale(true);
      return null;
    }
  }, [showId, take]);

  useEffect(() => {
    let source: EventSource | null = null;
    let timer: number | undefined;
    let fails = 0;
    let polling = typeof EventSource === "undefined";

    const poll = () => {
      polling = true;
      setPolling(true);
      window.clearInterval(timer);
      timer = window.setInterval(() => void refresh(), POLL_MS);
    };
    const open = () => {
      if (polling) return poll();
      source = new EventSource(`/api/shows/${showId}/stream`);
      source.addEventListener("snapshot", (e) => {
        fails = 0;
        take(JSON.parse((e as MessageEvent<string>).data) as SeatSnapshot, Date.now());
      });
      source.addEventListener("closed", () => {
        source?.close();
        void refresh(); // the show was cancelled: let the page say so
      });
      source.onerror = () => {
        setStale(true); // cleared by the next snapshot, from the reconnect or the poll
        // CLOSED: the API refused the stream (503, 410…); CONNECTING: it dropped and retries.
        if (source?.readyState === EventSource.CLOSED || ++fails >= STREAM_FAILS) {
          source?.close();
          source = null;
          void refresh();
          poll();
        }
      };
    };
    const close = () => {
      source?.close();
      source = null;
      window.clearInterval(timer);
    };
    const onVisible = () => {
      if (document.visibilityState !== "visible") return close();
      void refresh();
      open();
    };

    open();
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      close();
      document.removeEventListener("visibilitychange", onVisible);
      inFlight.current?.abort();
    };
  }, [refresh, showId, take]);

  /** Mark seats someone else just took (a 409) without waiting for the next update. */
  const markHeld = useCallback((ids: string[]) => {
    setState((prev) => {
      const held = new Map(prev.held);
      for (const id of ids) if (!prev.sold.has(id)) held.set(id, new Date(Date.now() + 600_000).toISOString());
      return { ...prev, held };
    });
  }, []);

  return { state, snapshot, offset, stale, polling, refresh, markHeld };
}
