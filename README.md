# Frontrow

**Pick your seat, live.** Movie and concert ticketing for Bengaluru with a live seat map: seats are held for 10 minutes the moment you tap them and grey out for everyone else.

> Status: **lifecycle steps 1–7 complete (2026-09-15) · next: step 8 Project Setup = milestone 1.0.** One of six portfolio projects by [Viraj Domadia](https://virajdomadia.vercel.app). **Live (landing page):** https://frontrow-viraj.vercel.app — will move to `frontrow.virajdomadia.com`.

## What it proves
Concurrency-safe seat holds (Redis Lua, all-or-none) · a Postgres unique guard on confirm · idempotent Razorpay webhooks incl. paid-after-expiry refunds · realtime over SSE on serverless · a showcase-grade SVG seat map for three venue templates

## Versions
| | Ships | ~Hours |
|---|---|---|
| **v1 Box office** (base) | Browse, event page, seat map, 10-min holds, Razorpay, QR ticket, my tickets, organiser console (venues from templates, events, showtimes, bookings) | 18 |
| **v2 Live hall** (mid) | Realtime seat state (two-tab demo), live sales dashboard, QR check-in, ticket email | 10 |
| **v3 Full house** (advanced) | Waitlist with auto-offer, best-available pick, dynamic pricing, seat-view preview, ticket transfer, seat heatmap | 10 |
| **v4 In your pocket** (mobile app) | Expo (React Native) app on the same API: seat map with gestures, offline QR wallet, push for expiring holds, organiser camera scanner | 15 |

## Stack
`web/` Next.js 15 (App Router) · TypeScript · Tailwind 4 — `api/` FastAPI (Python 3.12) · SQLAlchemy + Alembic · Neon Postgres · Upstash Redis · Razorpay · Resend — Vercel for both — `mobile/` (v4) Expo · React Native · TypeScript

## Docs (steps 1–7)
[PRD](PRD.md) · [Requirements](docs/03-requirements.md) · [User flows + screen index](docs/03-user-flows.md) · [Technical design](docs/04-technical-design.md) · [UI mockups](docs/04-ui-mockups.md) · [Architecture](docs/05-architecture.md) · [Data + API](docs/06-data-and-api.md) · [Development plan](docs/07-plan.md)

## In this repo
```
web/        Next.js app — the landing page lives here
api/        FastAPI backend — folder structure only until milestone 1.0
mobile/     Expo app — arrives in v4
docs/       lifecycle steps 3–7
mockups/    landing.html (ported to web/) · direction-variants.html (A–D, B chosen) · screens.html (all v1 screens) · img/ CC photos
brand/      logo, mark, favicon
PRD.md      product requirements v1 with locked decisions
```

### Run the landing page
```
cd web
pnpm install
pnpm dev
```
