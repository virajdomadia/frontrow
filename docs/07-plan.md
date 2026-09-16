# Frontrow — Development Plan

**Lifecycle step:** 7 of 17 · **Written:** 2026-09-15 · **Inputs:** [03-requirements.md](03-requirements.md), [04-technical-design.md](04-technical-design.md), [06-data-and-api.md](06-data-and-api.md).
**Tracker:** row status lives at https://claude.ai/artifact/SYCP9jsFMK9fgkoyCyq8DA (updated per milestone).
**Budget:** v1 ≈ 18 h · v2 ≈ 10 h · v3 ≈ 10 h · v4 ≈ 14 h. v1 carries two small app-readiness items (bearer tokens in F4, DOM-free seat-map core in F1) so v4 is a second renderer, not a rewrite. **Cadence:** evenings/weekends; each row = one branch + one PR, squash-merged, and **every PR shows something in the browser**. Milestones end deployed.

**Lean rules in force** (2026-09-15): setup is the minimum to deploy both apps with plain CI; no observability, contract gates, e2e workflows or tracker updates per PR; review findings fixed on the same branch; tests only from 04 §11. Hours saved go to the seat map, motion and content. **Accounts and keys are created just-in-time** — in the row that first needs them, never in a setup batch (Viraj, 2026-09-15): Neon in S2, Upstash in F2, Razorpay in F5, Resend + Blob in L5, Expo/EAS in M1/M8, Vercel Cron in M6.

How the lifecycle maps: step 8 = milestone 1.0; steps 9–11 and 14–15 cycle inside every row; step 12 is one checklist row at the end of v1; step 13 is the CI file in 1.0; step 16 is skipped unless something breaks; step 17 is a short doc after v3.

Column key — **Who:** 🟢 customer · 🔴 organiser · ⚪ platform. Endpoints from 06 §C; screens from 03-user-flows.

---

## v1 — Box office (≈ 18 h)

### Milestone 1.0 — Skeleton + catalog live (≈ 4.5 h) — step 8
Goal: both apps deployed, DB seeded, direction chosen, a visitor can browse real shows.

| # | Part | Who | web/ | api/ | Est. | Done when |
|---|---|---|---|---|---|---|
| S1 | **Direction + tokens** | 🟢 | Variant page per [04-ui-mockups.md](04-ui-mockups.md) (S4 + S3, 3–4 variants, live motion candidates, CC photos) → Viraj picks → tokens + fonts in `globals.css`, themed browser surfaces | — | 1.5 h | Chosen direction recorded in 04-ui-mockups; landing restyled only if tokens changed |
| S2 | **API skeleton + DB + seed** | ⚪ | `next.config.ts` rewrite `/api/*`; `lib/api.ts` typed fetch; `pnpm gen:api` | `pyproject` (uv), `main.py`, settings, error envelope, `/health`; SQLAlchemy models + Alembic `0001_v1` (06 §A); `services/layouts.py` three template generators; `seed/` — 3 venues, 8 events, ~20 showtimes relative to now, scattered sold seats, `CREDITS.md`; **accounts needed here and no others:** Vercel project `frontrow-api` (FastAPI preset, bom1) + Neon project (`DATABASE_URL`); `ci.yml` (web typecheck+build · api ruff+pytest) | 1.5 h | `api.frontrow…/docs` opens in prod; seed idempotent; CI green |
| S3 | **Events list + event page** | 🟢 | S2 `/events` with URL filters + empty state; S3 `/events/[slug]` with showtimes by day → venue, fill badge, JSON-LD; landing "Now showing" strip from `/home`; demo-login buttons (wired in F5) | `GET /events`, `/events/{slug}`, `/home`; `showtime_fill` view; `s-maxage=60` | 1.5 h | Live at production with seeded content; Lighthouse mobile ≥ 90 on both |

### Milestone 1.1 — Seat map + holds (≈ 6 h) 🟢 — the project's core
| # | Part | Who | web/ | api/ | Est. | Done when |
|---|---|---|---|---|---|---|
| F1 | **Seat map renders all three templates** | 🟢 | `components/seat-map/core.ts` — pure TS, no DOM: layout → positions, hit-test (point → seat id), `SeatState` + diff merge (v4's React Native map reuses it unchanged); `<SeatMap>` renders it as SVG from `Layout`; tier legend + prices; sold/held/mine classes; arena overview → wedge zoom (`viewbox.ts`), pan/zoom, pinch; keyboard roving + SR list; sticky footer with total; **the chosen motion signature (load moment)** | `GET /showtimes/{id}`, `/venues/{id}/layout`, `GET /showtimes/{id}/seats` (sold from Postgres, held from Redis hash) | 2.5 h | All three seeded venues render at 390 px and 1440 px; states from the API show correctly; reduced-motion honoured |
| F2 | **Hold engine** | ⚪ | `useSeatState` polling 5 s; tap → `POST /holds` with full selection; 409 toast + drop seat; deselect → `DELETE`; countdown (rAF clock, tab title, **hold-moment motion**) | **Upstash Redis created here** (`REDIS_URL`); `services/holds.py` Lua acquire/release + `holds:{st}` hash + version; `fr_sid` cookie; rate limit; **tests:** concurrent race, all-or-none, expiry | 2.5 h | Two tabs (5 s poll) can't both hold F7; tests green in CI |
| F3 | **Fill + polish** | 🟢 | Filling-fast badge uses held+sold; empty/sold-out states on S4; skeleton loading; error states (Redis down → "try again") | `HLEN` merge into fill | 1 h | Sold-out showtime disabled on S3 and explained on S4 |

### Milestone 1.2 — Pay + tickets (≈ 4.75 h) 🟢
| # | Part | Who | web/ | api/ | Est. | Done when |
|---|---|---|---|---|---|---|
| F4 | **Auth** | ⚪ | S9 sign-in/up with role picker; inline sign-in on checkout; demo buttons on landing | `/auth/*`, sessions (`kind` web\|mobile), argon2, `fr_sid` adoption; `/auth/demo`; **`POST/DELETE /auth/token`** bearer flow so v4 needs no auth work | 1.25 h | Demo customer signs in from landing in one click; organiser routes 403 for customers |
| F5 | **Checkout + Razorpay** | 🟢 | S5 checkout (seats, tiers, fee, total, countdown); Razorpay modal; `verify` fast path; "confirming…" poll; S8 refunded state | **Razorpay test account + webhook created here** (`RAZORPAY_*`); `POST /orders` (server totals), `GET /orders/{id}`, `POST /orders/{id}/verify`, `POST /webhooks/razorpay` (HMAC, dedupe, confirm tx, paid-after-expiry refund, `payment.failed`); lazy expiry; **tests:** signature+replay, confirm unique, paid-after-expiry ×2, total | 2.5 h | Test-mode payment produces tickets; replaying the webhook does nothing; both refund branches tested |
| F6 | **Tickets** | 🟢 | S6 ticket page with QR per seat + calendar link (**confirm-moment motion if chosen**); S7 my tickets upcoming/past | `GET /tickets/{order_id}`, `GET /my/tickets`, token signing | 1 h | QR decodes to a token the API verifies; other user's URL → 404 |

### Milestone 1.3 — Organiser console + close v1 (≈ 3 h) 🔴
| # | Part | Who | web/ | api/ | Est. | Done when |
|---|---|---|---|---|---|---|
| F7 | **Venues + events + showtimes** | 🔴 | S10 template picker with knobs and live layout preview (reuses `<SeatMap>`); S11 event form + list; S12 showtime form with tier prices, cancel guard | `/organiser/venues|events|showtimes` CRUD, ownership checks, slug, `has_sales` guard | 2 h | New organiser: sign-up → bookable showtime in < 3 min |
| F8 | **Bookings + v1 close** | 🔴 | S13 bookings list + CSV; README "how the hold engine works" with diagram; `docs/12-security-performance.md` one-page checklist + Lighthouse numbers | `/organiser/showtimes/{id}/bookings`; security list from 05 §7 walked | 1 h | v1 tagged; portfolio case-study entry drafted |

**v1 total ≈ 18.25 h**

---

## v2 — Live hall (≈ 10 h)

### Milestone 2.0 — Live map (≈ 4.5 h) 🟢
| # | Part | web/ | api/ | Est. | Done when |
|---|---|---|---|---|---|
| L1 | **SSE stream** | `useSeatState` opens `EventSource`, applies diffs, `Last-Event-ID`, falls back to polling; **ripple-take motion** on others' holds | `services/stream.py` generator (version poll 1 s + wake at next expiry, ping 20 s, close at 280 s); `vercel.json` maxDuration 300 | 3 h | Two tabs: hold/release/sale visible ≤ 1 s; Playwright test (1.5 s tolerance) |
| L2 | **Demo mode on landing** | "Try it live" section: two embedded mini seat maps of the same showtime side by side, driven by the real stream | — | 1.5 h | The wow works without opening two tabs |

### Milestone 2.1 — Organiser live + check-in + email (≈ 5.5 h) 🔴
| # | Part | web/ | api/ | Est. | Done when |
|---|---|---|---|---|---|
| L3 | **Dashboard** | S14 revenue, sold, fill per showtime, mini maps, last 20 orders, live via stream | `/organiser/dashboard`, organiser stream variant | 2 h | Purchase in another tab updates numbers |
| L4 | **Check-in** | S15 camera (`BarcodeDetector`) or paste; valid/used/invalid states | `POST /checkin` with single-use update | 1.5 h | Second scan → "already checked in HH:MM" |
| L5 | **Email + uploads** | Poster upload fields | **Resend key + Vercel Blob store created here**; Resend ticket email (React Email, QR), forgot-password; Blob upload route | 2 h | Ticket email arrives with working link |

---

## v3 — Full house (≈ 10 h)

### Milestone 3.0 — Waitlist + best available (≈ 5 h)
| # | Part | web/ | api/ | Est. | Done when |
|---|---|---|---|---|---|
| A1 | **Waitlist** | S16 join form on sold-out S4; offer email → claim → checkout with the exclusive hold | `waitlist` table, offer on release/refund (hook in `holds.release` + refund path), 10-min exclusive hold, expiry → next; **test** lapse→offer→claim | 3 h | Test green; e2e: sold out → release → offer → pay |
| A2 | **Best available** | "Pick for me" (count, tier) → preview highlight → hold | `GET /showtimes/{id}/best` — contiguous, centre-weighted, tier-filtered | 2 h | Returns contiguous when possible; explains when not |

### Milestone 3.1 — Pricing, transfer, heatmap, seat view (≈ 5 h)
| # | Part | web/ | api/ | Est. | Done when |
|---|---|---|---|---|---|
| A3 | **Dynamic pricing** | Organiser toggle + thresholds on S12; S4 shows current price and "rises at 75 %" | `showtime_pricing_rules`, price computed at hold and frozen into `order_seats` | 1.5 h | Shown price = charged price, always |
| A4 | **Ticket transfer** | S17 transfer action + claim page | `ticket_transfers`, `token_version` rotate | 1.5 h | Old QR rejected at check-in |
| A5 | **Heatmap + seat view** | S18 colour scale on `<SeatMap>`; section hover shows "view from here" photo | `/organiser/venues/{id}/heatmap` aggregate; seat-view photos in seed | 2 h | Heatmap matches seeded sales |

---

## v4 — In your pocket (≈ 15 h) — Expo app in `mobile/`

### Milestone 4.0 — App browses and books (≈ 6.75 h)
| # | Part | mobile/ | api/ | Est. | Done when |
|---|---|---|---|---|---|
| M1 | **Shell + auth** | Expo Router tabs, brand tokens/splash/icon, sign-in/up/demo, SecureStore token, generated API types | — (token flow shipped in F4) | 1.5 h | Demo login works on a phone against the production API |
| M2 | **Shows + event page** | Lists, filters, event page, showtimes — same endpoints | — | 1.5 h | Parity with S2/S3 |
| M3 | **Seat map + holds** | `react-native-svg` renderer over the shared `seat-map/core.ts`, pinch/pan, tap → hold, countdown header, polling (SSE if v2 shipped) | — | 2.25 h | Hold in app greys the seat on web ≤ 1 s |
| M4 | **Pay + tickets** | Razorpay RN SDK, order poll, ticket screen with QR | — | 1.5 h | Test-mode payment → ticket in app |

### Milestone 4.1 — The native reasons (≈ 7 h)
| # | Part | mobile/ | api/ | Est. | Done when |
|---|---|---|---|---|---|
| M5 | **Offline wallet** | SQLite cache of tickets + tokens, brightness boost, add-to-calendar | — | 2 h | Airplane mode: ticket opens and scans |
| M6 | **Push** | expo-notifications registration, deep links | `device_tokens`, `push_jobs`, job at hold time, `POST /internal/push/due` + Vercel Cron | 2.5 h | Backgrounded hold → notification at T-2:00 → deep link lands on the map |
| M7 | **Organiser scanner** | Scan tab: camera, haptics, running count | (uses v2 `POST /checkin`) | 1.5 h | 20 scans/min; duplicate → "already checked in" |
| M8 | **Ship** | EAS Android build, Expo Go link, landing "Get the app" block with QR, README GIF | — | 1 h | Reviewer installs from the landing page in < 1 min |

**Then:** `docs/17-post-launch.md` (½ page) and the portfolio case study. Total ≈ 52 h.

---

## Whole-product summary
| Version | Milestones | Hours | Cumulative |
|---|---|---|---|
| v1 Box office | 1.0 – 1.3 | 18 | 18 |
| v2 Live hall | 2.0 – 2.1 | 10 | 28 |
| v3 Full house | 3.0 – 3.1 | 10 | 38 |
| v4 In your pocket | 4.0 – 4.1 | 14 | 52 |
| Add-ons (in priority order) | A embed widget (4) · B on-sale alerts + calendar (2) · C accessible seating (3) · D organiser refunds (4) · E offline check-in PWA (3) · F group booking, split pay (8) · G season pass (4) · H layout CSV import (4) | up to 32 | up to 84 |

## Add-ons (only from time saved)
Taken in this order, each only when its enclosing version is fully done including docs, and only if the version came in under budget. None is a version; none changes the engine. All free to run.

| # | Add-on | What | Version it extends | ~h |
|---|---|---|---|---|
| A | **Embed widget** | A `<script>` tag a cinema pastes into its own site that renders the live seat map + Book flow for one showtime (iframe over `/embed/[showtimeId]`, same API, same SSE) — the map has reach beyond Frontrow | v2 | 4 |
| B | **On-sale alerts + calendar** | "Notify me when tickets go on sale" for a draft event (Resend); `.ics` per ticket and an iCal feed per venue | v2 | 2 |
| C | **Accessible seating** | Wheelchair + companion seat pairs in the layout templates, a filter on the map, and the full keyboard/screen-reader pass on the SVG (v3's stretch made real) | v3 | 3 |
| D | **Organiser refunds** | Cancel a showtime → automatic Razorpay refunds for every paid order + email; partial refund per ticket from the bookings list (v1 out-of-scope, lifted) | v3 | 4 |
| E | **Offline check-in PWA** | The v2 check-in page as an installable PWA that caches the showtime's valid tokens and syncs `checked_in_at` when back online — works in a basement hall with no signal | v2 | 3 |
| F | **Group booking, split pay** | One hold for the group, a share link, each friend pays their seat through Razorpay; the hold extends while ≥ 1 seat is paid; unpaid seats release at expiry | v3 | 8 |
| G | **Season pass** | Organiser sells a pass (N shows, a price); pass holders redeem seats at checkout without paying; pass QR at check-in | v3 | 4 |
| H | **Layout CSV import** | Organiser uploads a CSV of sections/rows/seats/tiers for a venue that fits no template; validated, rendered with the same map | v1 | 4 |

