# PRD — Frontrow: Movie/concert ticketing with live seat map

**Status:** v1 · lifecycle steps 1–7 complete (2026-09-15) — see [docs/](docs/) · next: step 8 Project Setup (= milestone 1.0)
**Name:** Frontrow · *pick your seat, live*
**URL:** https://frontrow.virajdomadia.com (landing live at https://frontrow-viraj.vercel.app until DNS)
**Slot:** #2 · Budget ~52 h (v1 18 · v2 10 · v3 10 · v4 14) · Build second
**Live artifacts:** [Tracker](https://claude.ai/artifact/SYCP9jsFMK9fgkoyCyq8DA) (plan rows with status, all docs, mockups, project data) · [Screens](https://claude.ai/artifact/MCedtstCq6C2o7d9vJacPp) (all 13 v1 screens, direction B) · [Direction variants](https://claude.ai/artifact/LFJw5Zg1LEvvYjqdhot2Dr) (A–D, B chosen) · Landing: https://frontrow-viraj.vercel.app

## One-liner
BookMyShow-style ticketing for Bengaluru: pick seats on a live map, they're held for you for 10 minutes and grey out for everyone else, pay with Razorpay, get a QR ticket.

## Who it's for
- **Customer:** someone booking seats for a movie or a concert.
- **Organiser:** a cinema, hall or promoter creating venues, events and showtimes and watching sales.
- **Platform (Frontrow):** the marketplace in between — sees everything, seeds the demo data.

## Why this project
- The seat-hold problem (two people, one seat, same second) is a classic system-design interview question — this is it, built for real, with a test that proves it.
- The most visual of the six: a seat map is the UI, and the two-tab demo needs no explanation.

## Locked decisions (2026-09-15) — follow these until the project ends

### 1. Identity: a ticketing *platform*, not a venue
Frontrow is the marketplace. Organisers sign up and create venues (from templates), events and showtimes; customers book. Three sides — customer, organiser, platform — so the "owner half" of the business is a real organiser console, not an internal admin. City: Bengaluru only (no city switcher).

### 2. Seed content: fictional, plausible, photographed
Shows and venues are **fictional but plausible** — no real movie posters or artists (rights). Photos are CC from Wikimedia Commons with credits. Three venues on three layout templates, ~8 events (movies and concerts), ~20 showtimes over the next 14 days:

| Venue | Template | Seats | Why |
|---|---|---|---|
| A 2-screen cinema | **Grid** — rows A–N, centre aisle, 3 tiers (Classic / Prime / Recliner) | ~180 / screen | The everyday case; the dense grid the seat map must nail |
| An auditorium | **Stalls + balcony** — two blocks, curved rows, 3 tiers | ~600 | Concerts and theatre; sections and a stage |
| A seated arena | **Tiered sections** — 8 wedge sections around a floor, 4 tiers | ~1,500 | Pan/zoom, section → seat drill-down, the "big venue" story |

Two demo logins on the landing page: a customer and an organiser.

### 3. Versions — base → mid → advanced → mobile app
Every project is cut base → mid → advanced (rule set 2026-09-15); Frontrow adds a fourth, a native app (Viraj, 2026-09-15). v1 alone is a complete, sellable ticketing site.

| Version | Ships | Proves | ~Hours |
|---|---|---|---|
| **v1 Box office** (base) | Browse movies & concerts, event page, showtimes, interactive seat map from templates, atomic 10-min Redis holds with countdown, Razorpay checkout, QR ticket, my tickets, customer auth. Organiser: sign up, venue from template, events, showtimes, price tiers, bookings list. Seat state polled every 5 s | Concurrency-safe holds, transactions, idempotent payments — a real ticketing site | 18 |
| **v2 Live hall** (mid) | Realtime seat state over SSE (the two-tab wow, expiry release ≤ 1 s), live sales dashboard (revenue, occupancy per show), check-in page that validates the QR, ticket email | Realtime on serverless, the demo moment | 10 |
| **v3 Full house** (advanced) | Waitlist for sold-out showtimes (auto-offer when a hold lapses), "best available" auto-pick, dynamic pricing that rises with occupancy, seat-view preview, ticket transfer to a friend, organiser seat-popularity heatmap | Features no template ticketing site has | 10 |
| **v4 In your pocket** (mobile app) | Native iOS/Android app on Expo (React Native, TypeScript) against the same API: browse, seat map with pinch/pan, holds, Razorpay, an offline ticket wallet with QR, push notifications (hold expiring, waitlist offer), organiser check-in with the camera. Installable Android build + Expo Go for iOS | The API is a real product core; one more platform, zero new backend logic | 14 |

### 4. The engine: Redis holds + Postgres guard + SSE
- **Holds** live only in Redis (Upstash): one Lua script takes all requested seats or none (`SET NX EX 600` per seat + `INCR` a per-showtime version counter); a conflict returns the seats that were taken.
- **Sold** lives in Postgres: `tickets` has `UNIQUE (showtime_id, seat_id)` — the final guard on confirm, so even a Redis mishap can't double-sell.
- **Realtime** is SSE from FastAPI on Vercel (v2): a loop per open seat map checks the version counter once a second and wakes at the next known hold expiry, so releases are visible within ~1 s. No WebSockets, no separately hosted server — Vercel functions can't hold WS, and free long-running hosts spin down and would kill the demo with a cold start.
- **Payments:** Razorpay Checkout (test mode) + webhook, deduplicated by event id. *Paid after the hold expired:* seats still free → sell them anyway; already sold to someone else → automatic Razorpay refund, order marked refunded.
- **QR ticket:** signed token; the check-in page (v2) verifies it and marks the ticket used once.

### 5. Stack and setup — lean
Shared stack from [`projects/README.md`](../README.md): `web/` Next.js App Router + Tailwind 4, `api/` FastAPI on Vercel (FastAPI preset), Neon Postgres, Upstash Redis, Razorpay, own cookie-session auth, Resend for email (v2). Setup is the minimum to deploy both apps with plain CI (web typecheck + build, api pytest). OpenAPI → TS types generated by a script and committed; no CI freshness gate, no Sentry, no uptime monitor unless a feature needs it.

Tests only where a demo bug would embarrass: two parallel holds on one seat → exactly one wins; ticket uniqueness on confirm; webhook signature + idempotency; paid-after-expiry; order totals.

## The wow moment (v2)
Open two tabs on the same showtime. Pick a seat in one — it greys out in the other before your finger leaves the trackpad. Let the timer run out and watch it come back in both.

## Out of scope (all versions)
Custom venue-layout editor (templates only) · refunds UI (only the automatic paid-after-expiry refund) · App Store / Play Store listing (v4 ships as an Android build + Expo Go, not a store release) · real-money mode · multi-city · reserved standing/GA zones · promo codes · seat-map accessibility beyond keyboard + screen-reader seat list (full WCAG pass on the SVG map is a v3 stretch).

## Success criteria
- Two concurrent requests for the same seat can never both succeed — covered by a test that runs in CI.
- A confirmed booking always corresponds to exactly one ticket row per seat (unique constraint, tested).
- v2: a hold expiry or new hold is visible to every open seat map within ~1 s.
- Lighthouse mobile ≥ 90 perf / 100 a11y / 100 SEO on landing, events list and event page.
- A visible frontend signature: the seat map's authored motion (chosen in step 4), themed browser surfaces, reduced-motion fallbacks.

## Resolved questions
- *Movies vs concerts?* Both — the two template families are the point of the seat map.
- *WebSocket vs SSE?* SSE from FastAPI on Vercel; see decision 4.
- *Who is the admin?* Organiser accounts (platform model); see decision 1.
- *Mobile app?* Yes, as v4 on Expo — the web app stays the primary product; the app proves the API core is reusable and adds the two things only native does well: an offline ticket wallet and push.
