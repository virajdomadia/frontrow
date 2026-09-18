# Frontrow

**Pick your seat, live.** Movie and concert ticketing for Bengaluru with a live seat map: seats are held for 10 minutes the moment you tap them and grey out for everyone else.

> Status: **step 8 in progress — milestone 1.0 (2026-09-18): S1 direction ✅ · S2 API skeleton + DB + seed ✅ · S3 events list + event page next.** One of six portfolio projects by [Viraj Domadia](https://virajdomadia.vercel.app). **Live (landing page):** https://frontrow-viraj.vercel.app — will move to `frontrow.virajdomadia.com`.

## What it proves
Concurrency-safe seat holds (Redis Lua, all-or-none) · a Postgres unique guard on confirm · idempotent Razorpay webhooks incl. paid-after-expiry refunds · realtime over SSE on serverless · a showcase-grade SVG seat map for three venue templates

## Versions
| | Ships | ~Hours |
|---|---|---|
| **v1 Box office** (base) | Browse, event page, seat map, 10-min holds, Razorpay, QR ticket, my tickets, organiser console (venues from templates, events, showtimes, bookings) | 18 |
| **v2 Live hall** (mid) | Realtime seat state (two-tab demo), live sales dashboard, QR check-in, ticket email | 10 |
| **v3 Full house** (advanced) | Waitlist with auto-offer, best-available pick, dynamic pricing, seat-view preview, ticket transfer, seat heatmap | 10 |
| **v4 In your pocket** (mobile app) | Expo (React Native) app on the same API: seat map with gestures, offline QR wallet, push for expiring holds, organiser camera scanner | 14 |

## Stack
`web/` Next.js 15 (App Router) · TypeScript · Tailwind 4 — `api/` FastAPI (Python 3.12) · SQLAlchemy + Alembic · Neon Postgres · Upstash Redis · Razorpay · Resend — Vercel for both — `mobile/` (v4) Expo · React Native · TypeScript

## Live artifacts
[Tracker](https://claude.ai/artifact/SYCP9jsFMK9fgkoyCyq8DA) — plan v1–v4 with row status, every doc rendered, mockups live, project data · [Screens](https://claude.ai/artifact/MCedtstCq6C2o7d9vJacPp) — all 13 v1 screens in direction B · [Direction variants](https://claude.ai/artifact/LFJw5Zg1LEvvYjqdhot2Dr) — A/B/C/D, B chosen 2026-09-15

## Docs (steps 1–7)
[PRD](PRD.md) · [Requirements](docs/03-requirements.md) · [User flows + screen index](docs/03-user-flows.md) · [Technical design](docs/04-technical-design.md) · [UI mockups](docs/04-ui-mockups.md) · [Architecture](docs/05-architecture.md) · [Data + API](docs/06-data-and-api.md) · [Development plan](docs/07-plan.md)

## In this repo
```
web/        Next.js app — landing page, typed api client (src/lib/api.ts), seed photos (public/img)
api/        FastAPI backend — models + Alembic, layout generators, seed (python -m app.seed)
mobile/     Expo app — arrives in v4
docs/       lifecycle steps 3–7
mockups/    landing.html (ported to web/) · direction-variants.html (A–D, B chosen) · screens.html (all v1 screens) · img/ CC photos
brand/      logo, mark, favicon
PRD.md      product requirements v1 with locked decisions
```

### Run it
```
# api — needs Postgres (api/.env.example has a local URL); uv installs Python 3.12
cd api && uv sync && cp .env.example .env.local
uv run alembic upgrade head && uv run python -m app.seed      # seed is idempotent
uv run uvicorn app.main:app --reload --port 8000               # http://localhost:8000/docs

# web — proxies /api/* to API_URL (web/.env.example)
cd web && pnpm install && cp .env.example .env.local && pnpm dev

pnpm gen:api   # in web/: regenerate api/openapi.json + src/lib/api-types.ts after changing the contract
```
Demo logins (seeded): `customer@frontrow.demo` / `organiser@frontrow.demo`, password `frontrow-demo`.
