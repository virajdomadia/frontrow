/**
 * The map camera: an SVG viewBox in layout units, always the same aspect as the panel, so a
 * screen point maps to a layout point with one scale. Framework-free like `core.ts` — the
 * React component (and v4's gesture handler) only feed it pointer deltas.
 *
 * Scale = CSS px per layout unit; a seat is `SEAT * scale` px on screen.
 */

import { SEAT, type Box, type Point } from "./core";

export type Size = { w: number; h: number };

/** A seat must be ≥ 24 px to be a fair tap target (04-ui-mockups). */
export const MIN_TAP_PX = 24;
/** Below this a tap picks a section, not a seat (the arena overview). */
export const OVERVIEW_PX = 16;
export const MAX_SCALE = 3;

export const scaleOf = (box: Box, view: Size) => view.w / box.w;
export const seatPx = (box: Box, view: Size) => SEAT * scaleOf(box, view);

/** The box at `scale` centred on `c`. */
export function boxAt(c: Point, scale: number, view: Size): Box {
  const w = view.w / scale;
  const h = view.h / scale;
  return { x: c.x - w / 2, y: c.y - h / 2, w, h };
}

/** Fit `content` (plus `pad` layout units) inside the view, centred. */
export function fit(content: Box, view: Size, pad = 0): Box {
  const scale = Math.min(view.w / (content.w + pad * 2), view.h / (content.h + pad * 2));
  return boxAt({ x: content.x + content.w / 2, y: content.y + content.h / 2 }, scale, view);
}

/** Fit `target`, but never smaller than `minScale` (e.g. seats ≥ 24 px when zooming a wedge). */
export function focus(target: Box, view: Size, minScale: number, pad = 0): Box {
  const fitted = fit(target, view, pad);
  const scale = Math.min(MAX_SCALE, Math.max(scaleOf(fitted, view), minScale));
  return boxAt({ x: target.x + target.w / 2, y: target.y + target.h / 2 }, scale, view);
}

/**
 * Keep the camera sane: scale between "whole layout fits" and MAX_SCALE, and the content never
 * slides out of view — an axis that fits is centred, one that doesn't is clamped to its edges.
 */
export function clamp(box: Box, content: Box, view: Size): Box {
  const minScale = scaleOf(fit(content, view), view);
  const scale = Math.min(MAX_SCALE, Math.max(minScale, scaleOf(box, view)));
  const w = view.w / scale;
  const h = view.h / scale;
  const axis = (pos: number, size: number, start: number, len: number) =>
    size >= len ? start + (len - size) / 2 : Math.min(Math.max(pos, start), start + len - size);
  const cx = box.x + box.w / 2;
  const cy = box.y + box.h / 2;
  return {
    x: axis(cx - w / 2, w, content.x, content.w),
    y: axis(cy - h / 2, h, content.y, content.h),
    w,
    h,
  };
}

/** Screen point (px from the panel's top-left) → layout point. */
export function toLayout(box: Box, view: Size, px: number, py: number): Point {
  const s = scaleOf(box, view);
  return { x: box.x + px / s, y: box.y + py / s };
}

/** Zoom by `factor` (> 1 = in) keeping the layout point under screen point (px, py) fixed. */
export function zoomAt(box: Box, view: Size, factor: number, px: number, py: number): Box {
  const anchor = toLayout(box, view, px, py);
  const w = box.w / factor;
  const h = box.h / factor;
  return { x: anchor.x - (px / view.w) * w, y: anchor.y - (py / view.h) * h, w, h };
}

/** Drag by screen px. */
export function panBy(box: Box, view: Size, dxPx: number, dyPx: number): Box {
  const s = scaleOf(box, view);
  return { ...box, x: box.x - dxPx / s, y: box.y - dyPx / s };
}

/** Pan the least needed so `p` sits at least `margin` layout units inside the box. */
export function ensureVisible(box: Box, p: Point, margin: number): Box {
  const x = p.x - margin < box.x ? p.x - margin : p.x + margin > box.x + box.w ? p.x + margin - box.w : box.x;
  const y = p.y - margin < box.y ? p.y - margin : p.y + margin > box.y + box.h ? p.y + margin - box.h : box.y;
  return x === box.x && y === box.y ? box : { ...box, x, y };
}

/** Keep the centre, change the aspect to a resized view's (layout units per px unchanged). */
export function resize(box: Box, from: Size, to: Size): Box {
  const s = scaleOf(box, from);
  return boxAt({ x: box.x + box.w / 2, y: box.y + box.h / 2 }, s, to);
}

const ease = (t: number) => 1 - (1 - t) ** 3; // ease-out cubic

/**
 * Tween the camera from `a` to `b`. Zoom interpolates in log space so a 4× zoom feels even.
 * Returns a cancel function. `ms` 0 (reduced motion) jumps straight to `b`.
 */
export function animate(a: Box, b: Box, ms: number, onFrame: (box: Box) => void): () => void {
  if (ms <= 0) {
    onFrame(b);
    return () => {};
  }
  const raf = globalThis.requestAnimationFrame;
  const cancelRaf = globalThis.cancelAnimationFrame;
  let handle = 0;
  let start = -1;
  const ca = { x: a.x + a.w / 2, y: a.y + a.h / 2 };
  const cb = { x: b.x + b.w / 2, y: b.y + b.h / 2 };
  const step = (now: number) => {
    if (start < 0) start = now;
    const t = ease(Math.min(1, (now - start) / ms));
    const w = Math.exp(Math.log(a.w) + (Math.log(b.w) - Math.log(a.w)) * t);
    const h = (w * a.h) / a.w;
    const cx = ca.x + (cb.x - ca.x) * t;
    const cy = ca.y + (cb.y - ca.y) * t;
    onFrame(t >= 1 ? b : { x: cx - w / 2, y: cy - h / 2, w, h });
    if (t < 1) handle = raf(step);
  };
  handle = raf(step);
  return () => cancelRaf(handle);
}
