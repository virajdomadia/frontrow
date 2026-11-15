# Frontrow

**Pick your seat, live.** A movie ticketing marketplace for Bengaluru with a live seat map: a seat is held for 10 minutes the moment you tap it and greys out for everyone else. Cinemas run their shows on it; Frontrow staff run the marketplace.

> Status: **re-planned 2026-11-15/16 — movies only, three roles.** Built so far: brand, API + database, shows pages, seat map (PRs #2–#13). Next: row B1 (films, cinemas, screens; the new paper + oxblood look; a catalogue that never empties). One of six portfolio projects by [Viraj Domadia](https://virajdomadia.vercel.app). **Live:** https://frontrow-viraj.vercel.app — moving to `frontrow.virajdomadia.com`.

## What it proves
Concurrency-safe seat holds (Redis Lua, all-or-none) · a Postgres unique guard on confirm · idempotent Razorpay webhooks incl. paid-after-expiry refunds · counter and online sales on one live map · a three-sided marketplace (customers, theatre owners, staff) with per-business access · live updates on serverless inside free tiers · a showcase-grade SVG seat map

## Versions
| | Ships | ~Hours |
|---|---|---|
| **v1 Box office** | Customer: BookMyShow's flow with an email code (home, movie, language/format, showtimes, how many seats, seat map + holds, Razorpay, M-ticket). Theatre owner: register, cinemas, screens, pick films, bulk shows, bookings, door scanning. Staff: film catalogue, requests, approvals | 26 left (+7 built) |
| **v2 Live hall** | Live seats, "Try it live" on the landing page, today board with live sales, blocked seats, counter sales, cancel a show; staff support, suspend, marketplace view | 13.75 |
| **v3 Full house** | Reviews after scan-in, waitlist, sales reports, payouts, seat heatmap, review moderation | 10 |
| **v4 In your pocket** | One Expo app, tabs per role: customer booking + offline wallet + push; owner scanner, today board, counter; staff approvals + support | 18.5 |

## Stack
`web/` Next.js 15 (App Router) · TypeScript · Tailwind 4 — `api/` FastAPI (Python 3.12) · SQLAlchemy + Alembic · Neon Postgres · Upstash Redis · Razorpay · Gmail SMTP — Vercel for both — `mobile/` (v4) Expo · React Native · TypeScript

## Live artifacts
[Tracker](https://claude.ai/artifact/SYCP9jsFMK9fgkoyCyq8DA) — plan v1–v4 by role with row status, every doc rendered, mockups, project data

## Docs (steps 1–7)
[PRD](PRD.md) · [Requirements](docs/03-requirements.md) · [User flows + screen index](docs/03-user-flows.md) · [Technical design](docs/04-technical-design.md) · [UI mockups](docs/04-ui-mockups.md) · [Architecture](docs/05-architecture.md) · [Data + API](docs/06-data-and-api.md) · [Development plan](docs/07-plan.md)

## In this repo
```
web/        Next.js app — landing page, shows pages, seat map, typed api client (src/lib/api.ts), seed photos (public/img)
api/        FastAPI backend — models + Alembic, layout generators, holds, seed (python -m app.seed)
mobile/     Expo app — arrives in v4
docs/       lifecycle steps 3–7 (re-planned 2026-11-15/16)
mockups/    direction-variants.html (B chosen) · screens.html + landing.html (before the re-plan) · img/ CC photos
brand/      logo, mark, favicon
PRD.md      product requirements with locked decisions
```

### Run it
```
# api — needs Postgres (api/.env.example has a local URL); uv installs Python 3.12
cd api && uv sync && cp .env.example .env.local
uv run alembic upgrade head && uv run python -m app.seed      # seed is idempotent
uv run uvicorn app.main:app --reload --port 8002               # http://localhost:8002/docs

# web — proxies /api/* to API_URL (web/.env.example)
cd web && pnpm install && cp .env.example .env.local && pnpm dev

pnpm gen:api   # in web/: regenerate api/openapi.json + src/lib/api-types.ts after changing the contract
```
Demo logins: one-click buttons on the landing page (customer, theatre owner, staff) once B2 ships; until then the S2 seed users exist. Ports 3000/8000 are used by another project on this machine, so the examples use 8002.
