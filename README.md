# Frontrow

**Pick your seat, live.** Movie and concert ticketing with a live seat map: seats are held for 10 minutes the moment you tap them and grey out for everyone else.

> Status: in progress — planning and design stage. One of six portfolio projects by [Viraj Domadia](https://virajdomadia.vercel.app). Will go live at `frontrow.virajdomadia.com`.

## What it proves
Concurrency and seat holds (Redis) · transactions · idempotent payments · realtime updates

## Stack
Next.js (App Router) · TypeScript · Tailwind CSS 4 · PostgreSQL (Neon) + Drizzle · Better Auth · Razorpay · Vitest + Playwright · Sentry · Vercel

## In this repo
- [`PRD.md`](PRD.md) — product requirements (v0, being refined)
- [`mockups/landing.html`](mockups/landing.html) — landing-page design mockup (open in a browser)
- [`brand/`](brand/) — logo, mark and favicon

## Roadmap
1. Finalise the PRD
2. Scaffold the Next.js app
3. Build the thin vertical slice described in the PRD
4. Tests, CI, Lighthouse, deploy
5. Case study on the portfolio
