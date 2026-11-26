"use client";

import { useEffect, useRef, useState } from "react";
import { mmss, remainingMs } from "@/components/booking/holds";

/**
 * The hold countdown (04 §3): one `requestAnimationFrame` clock that re-renders only when the
 * displayed second changes, mirrors `mm:ss` into the tab title, and calls `onZero` once.
 */
export function useCountdown(
  expiresAt: string | null | undefined,
  offset: number,
  { title, onZero }: { title?: string; onZero?: () => void } = {},
) {
  const [left, setLeft] = useState(() => remainingMs(expiresAt, Date.now(), offset));
  const zeroRef = useRef(onZero);
  zeroRef.current = onZero;

  useEffect(() => {
    if (!expiresAt) {
      setLeft(0);
      return;
    }
    let raf = 0;
    let shown = -1;
    let fired = false;
    const update = () => {
      const ms = remainingMs(expiresAt, Date.now(), offset);
      const second = Math.ceil(ms / 1000);
      if (second !== shown) {
        shown = second;
        setLeft(ms);
      }
      if (ms <= 0 && !fired) {
        fired = true;
        zeroRef.current?.();
      }
      return ms;
    };
    const tick = () => {
      if (update() > 0) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    // rAF pauses in a background tab; a coarse timer keeps the title and expiry honest there.
    const backup = window.setInterval(update, 1000);
    return () => {
      cancelAnimationFrame(raf);
      window.clearInterval(backup);
    };
  }, [expiresAt, offset]);

  const active = Boolean(expiresAt) && left > 0;
  useEffect(() => {
    if (!title) return;
    const base = title;
    document.title = active ? `${mmss(left)} · ${base}` : base;
  }, [title, left, active]);

  return { left, text: mmss(left), active };
}
