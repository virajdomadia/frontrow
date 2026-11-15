# Frontrow — Technical Design

**Lifecycle step:** 4 of 17 · **Locked:** 2026-09-15 · **Updated for the movies-only re-plan:** 2026-11-16 (venues → cinemas and screens, events → shared films, email-code sign-in, Gmail SMTP, arena dropped, push-on-change realtime, no crons) · UI companion: [04-ui-mockups.md](04-ui-mockups.md). Schema and routes: [06-data-and-api.md](06-data-and-api.md).

## 1. Stack (shared stack, no deviations)
| Layer | Choice | Notes |
|---|---|---|
| web/ | Next.js 15 App Router · TypeScript strict · Tailwind 4 · pnpm | UI only; `/api/*` rewritten to the API so cookies are same-origin |
| api/ | FastAPI (Python 3.12, uv) · SQLAlchemy 2.0 async + Alembic · pydantic · pytest | Vercel FastAPI preset, region `sin1` (next to Neon Singapore; Neon has no Mumbai), `maxDuration` 300 for the stream route |
| Data | Neon Postgres | Source of truth for everything sold |
| Holds / realtime | Upstash Redis (TCP client `redis-py` asyncio, not the REST client — Lua needs `EVALSHA`) | Holds, version counters |
| Payments | Razorpay Checkout + webhooks, test mode | |
| Email (v1) | Gmail SMTP from a dedicated Frontrow Gmail (app password), sender ported from Tripsmith | Sign-in codes, ticket emails; ~500/day; no Resend |
| Files | Vercel Blob, only if staff upload posters instead of linking them | Film posters |
| Contract | `api/openapi.json` → `openapi-typescript` → `web/src/lib/api-types.ts` | Script `pnpm gen:api`; committed; **not** CI-gated |
| CI | GitHub Actions: `web` (typecheck + build), `api` (ruff + pytest with Postgres + Redis services) | Nothing else |

## 2. Seat layouts

A **screen** (inside a cinema) has a **template** and **knobs**; the API generates `seats` rows once at venue creation and stores a `layout` JSON the map renders from. Seats are rows (not a blob) because holds, tickets and the heatmap key on `seat_id`.

```jsonc
// venues.layout
{ "template": "grid", "width": 1200, "height": 800,
  "stage": { "label": "SCREEN", "x": 100, "y": 40, "w": 1000 },
  "sections": [
    { "key": "stalls", "label": "Stalls", "tier": "classic",
      "shape": "rows",                       // rows | wedge
      "rows": [ { "label": "A", "seats": [ { "n": 1, "x": 120, "y": 140 }, … ] } ] }
  ] }
```

| Template | Knobs | Generator |
|---|---|---|
| `grid` | rows (8–20), seats per row (10–24), aisle after seat k, tier split by row bands | straight rows, y per row, gap at aisle |
| `stalls_balcony` | stalls rows/seats, balcony rows/seats, curve radius | rows on arcs, two blocks |

Tier per section; price per (show, tier). The arena template was dropped on 2026-11-15 (movies only); F1's arena code is removed in B1. Seat ids are stable UUIDs; the map keys on them.

## 3. The seat map (web)
- `seat-map/core.ts` is pure TypeScript with no DOM or React: layout → seat positions, hit-test (point → seat id), `SeatState` + `SeatDiff` merge, selection rules (max 10). Web and the v4 app both render it; only the renderer differs.
- One `<SeatMap>` component over the core: props `layout`, `state` (sold/held/mine + expiries), `selection`, `onToggle`. Renders **SVG** — `<g>` per section, `<rect rx>` per seat (fast up to ~2k nodes; the arena caps at ~1,500). Seat state is a CSS class, so state changes never re-render geometry.
- Grid and stalls + balcony fit to width; pan/zoom via pointer events + wheel and pinch on touch for dense screens. **How many seats** is chosen before the map; a tap selects that many adjacent seats in the row where possible.
- Keyboard: roving `tabindex` across seats within the focused section; arrows move by row/seat; Enter toggles. A visually-hidden `<ul aria-live>` announces selection and conflicts.
- Countdown: a single `requestAnimationFrame` clock driving CSS variables (`--t`) on held seats and the footer; tab title shows `mm:ss`.
- State source: `useSeatState(showId)` — v1 polls every 5 s sending its last `v` (the API answers `unchanged` from Redis alone, and the sold set is cached in Redis, so polling never wakes Neon); v2 receives pushes only on change and falls back to polling. Same payload shape both ways.
- Motion signature and visual direction: decided in [04-ui-mockups.md](04-ui-mockups.md) from 3–4 variants. Candidates on the table: hall lights sweeping the map on load; the hold countdown as a burning ring around each held seat; the ticket tearing along a perforation on confirm.

## 4. The hold engine (api)

**Redis keys**
```
hold:{showtime_id}:{seat_id}  = session_id     TTL 600 s
st:{showtime_id}:v            = int             INCR on every hold/release/sale
```

**Acquire (one Lua script, all-or-none)**
```lua
-- KEYS = hold keys for every requested seat; ARGV = session, ttl, version key
local taken, fresh = {}, {}
for i, k in ipairs(KEYS) do
  local v = redis.call('GET', k)
  if v == false then fresh[#fresh+1] = k
  elseif v ~= ARGV[1] then taken[#taken+1] = k end
end
if #taken > 0 then return { 0, taken } end
for i, k in ipairs(fresh) do redis.call('SET', k, ARGV[1], 'EX', ARGV[2]) end
if #fresh > 0 then redis.call('INCR', ARGV[3]) end   -- st:{showtime}:v
return { 1, #fresh }
```
Seats already held by the *same* session are re-granted (idempotent re-tap) but keep their original TTL: the script only `SET`s keys that were empty (`fresh`). Before Redis, the API checks Postgres for sold seats (one `SELECT seat_id FROM tickets WHERE showtime_id=…`), and a sold seat is a 409 too.

**Release** — `DEL` the session's keys (checked with a compare-and-delete Lua) + `INCR v`.

**Confirm** (webhook) — in one Postgres transaction: `INSERT INTO tickets …` (the `UNIQUE (showtime_id, seat_id)` raises on a double-sell → transaction aborts → refund path), `UPDATE orders SET status='paid'`, then outside the transaction `DEL` holds + `INCR v`. If Redis is unreachable the sale still commits — Redis is a fast path, Postgres is the guard.

**Why Redis, not Postgres-only:** TTL expiry for free, atomic multi-seat take via Lua with no row locks, and it is the answer interviewers expect. Postgres alone (a `holds` table with `expires_at` + `FOR UPDATE`) would work; the trade is a second service for the story and ~1 s expiry precision without a cron.

**Upstash budget (free tier 500k commands/month):** a hold is 1 script call; a v1 poll is 2 commands (`SMEMBERS`-like scan via `SCAN hold:{id}:*` → replaced by a per-showtime `HSET holds:{id}` mirror written by the same Lua so a snapshot is 1 `HGETALL` + 1 `GET`); a v2 stream is 1 `GET` per second per open map (~3,600/h). A two-hour demo across 5 tabs ≈ 36k commands. Fine.

> Implementation detail for the snapshot: the Lua script also writes `HSET holds:{showtime} {seat_id} "{session}|{expires_at_epoch}"` and the release/confirm paths `HDEL`. Individual `hold:` keys still carry the TTL; a snapshot drops hash entries whose `expires_at` is past (lazy cleanup, and a `HDEL` for them when found).

## 5. Realtime (v2): SSE on Vercel

> **Free-tier rule (2026-11-15):** the loop below checks Redis every second per open map (~3,600 commands per viewer-hour against Upstash's 500K/month) and holds a Vercel function open for minutes. Row L1 starts by redesigning it to push only on change (for example waking on a Redis publish, or long-polling on the version) before building. The contract (`snapshot` / `diff` events, `SeatState` shape) stays.
```
GET /showtimes/{id}/stream        text/event-stream, maxDuration 300
  event: snapshot  data: { v, sold:[…], held:[{seat_id, expires_at}], server_time }
  event: diff      data: { v, held:+[…] -[…], sold:+[…] }
  event: ping      every 20 s
```
Loop: `v = GET st:{id}:v`; if changed → build diff from `HGETALL holds:{id}` + sold set (sold set cached in-process and refreshed when `v` changes), emit; then `await sleep(min(1 s, next_expiry - now))`. At `next_expiry` the loop re-reads and emits the release even though `v` didn't change (TTL expiry doesn't bump `v`). After ~280 s the server closes the stream; `EventSource` reconnects with `Last-Event-ID = v`, and the server sends a full snapshot if it can't diff.

Why not WebSockets: Vercel functions can't hold them; a separately hosted always-on API on a free tier spins down (50 s cold start kills the two-tab demo). Why not a hosted realtime service (Ably/Pusher): it hides the part the project is meant to prove.

## 6. Payments
1. `POST /orders` → verify all seats held by this session (Redis) and not sold (Postgres) → compute total server-side from `price_tiers` (+ ₹30 fee/ticket) → `razorpay.order.create(amount, receipt=order_id)` → store → return `{ order_id, razorpay_order_id, amount, key_id }`.
2. Web opens Razorpay Checkout; on `handler` success it calls `POST /orders/{id}/verify` with the payment signature (fast path: confirms immediately if valid, same transaction as the webhook — both paths are idempotent through `orders.status`).
3. Webhook `POST /webhooks/razorpay`: HMAC check with the webhook secret, insert `webhook_events(id)` (PK → duplicate = no-op), then confirm as in §4. Returns 200 always after signature check so Razorpay stops retrying.
4. Paid-after-expiry: holds missing → try the insert anyway; on unique-violation → `razorpay.payment.refund(payment_id)` → order `refunded`, tickets none, `refund_reason = 'seat_sold'`.
5. Orders `pending` for > 15 min are treated as `expired` on read (no cron).

## 7. Tickets & QR
Token `= base64url(ticket_id:show_id:exp) . "." . hmac_sha256(secret, payload)[:16]`, exp = showtime end + 6 h. QR rendered client-side (`qrcode` package) from the token. Check-in (**v1, row B10**): `POST /checkin` with token → verify → `UPDATE tickets SET checked_in_at = now() WHERE id=… AND checked_in_at IS NULL` → 0 rows = already used.

## 8. Auth
**Email code only (2026-11-15).** `POST /auth/code` stores a hashed 6-digit code in Redis (10-minute TTL, 5 tries, 1/min + 5/h per email, per-IP limit) and emails it over Gmail SMTP; `POST /auth/verify` signs in, creating the user on first use. Three doors: customer, business (registration adds a `businesses` row + membership, status pending), staff (seeded `is_staff` users only; the door answers the same for any email). Demo users are never emailed. `sessions(id, user_id, sid, kind, expires_at)`, cookie `fr_session` HttpOnly SameSite=Lax. Anonymous visitors get a `fr_sid` cookie (random id) used for holds; sign-in re-keys their Redis holds to the user's session (`RENAME`-free: the hold value stays the sid, and the session records `sid`). Owner routes check membership of the business that owns the cinema / screen / show (another business's id → 404); staff routes check `is_staff`.

## 9. Caching & rendering
Events list and event pages: server-rendered, `Cache-Control: s-maxage=60` on the API GETs, tag revalidation on organiser edits. Seat map page: dynamic (`no-store`) — it is live data. Landing: static.

## 10. Failure modes worth handling
| Failure | Behaviour |
|---|---|
| Redis down | Holds fail with 503 "try again"; sales still confirm through Postgres |
| Webhook late (> 20 s) | Checkout shows "confirming…" and keeps polling; the `verify` fast path usually beats it |
| Two tabs, same session | Both see the seats as "mine"; deselect in one releases for both (same session) |
| Stream drops | `EventSource` reconnects; polling fallback after two failures |
| Clock skew | All expiries are server timestamps; the client offsets by `server_time - Date.now()` from the snapshot |

## 11. Testing (only these)
- `test_holds_concurrent`: 20 coroutines race for the same seat → exactly one success.
- `test_holds_all_or_none`: A holds F7; B requests F6+F7 → 409 with `["F7"]`, F6 untouched.
- `test_hold_expiry`: TTL 1 s in test → free after 1.2 s.
- `test_confirm_unique`: two confirms for one seat → one ticket, one refund path.
- `test_webhook_signature_and_replay`.
- `test_paid_after_expiry` both branches.
- `test_order_total`.
- `test_access_rules`: customer → owner/staff routes refused; another business's ids → 404.
- `test_otp`: expiry, 5 tries, rate limits.
- `test_checkin`: valid once, second scan `used`, wrong show.
- `test_show_overlap`: overlapping shows on one screen refused.
- v2: two pages, hold in one, grey in the other ≤ 1.5 s.

## 12. v4 — mobile app (Expo)
| Concern | Choice | Why |
|---|---|---|
| Framework | **Expo SDK (React Native, TypeScript), Expo Router** in `mobile/` next to `web/` and `api/` | One codebase for iOS + Android; React knowledge carries over; no Swift/Kotlin |
| API client | Same `openapi.json` → generated types (`mobile/src/lib/api-types.ts`); `fetch` with `Authorization: Bearer` | Zero duplicated contract |
| Auth | `POST /auth/token` (shipped in v1, B2, same email-code flow) returns an opaque bearer token (row in `sessions` with `kind='mobile'`, 90-day expiry); stored in `expo-secure-store` | Cookies don't fit native; same sessions table |
| Seat map | `react-native-svg` rendering the same `Layout` JSON; pinch/pan via `react-native-gesture-handler` + `reanimated`; seat state via polling (SSE via `react-native-sse` once v2 exists) | Same geometry as web, native gestures |
| Payments | `react-native-razorpay` (Checkout SDK); order / verify / webhook unchanged | |
| Wallet | `expo-sqlite` cache of the user's tickets + QR tokens; `expo-brightness` on the QR screen; `expo-calendar` | Offline is the reason a native app exists here |
| Push | `expo-notifications`. The hold reminder (T-2:00) is a **local notification scheduled on the phone** when the hold starts; booking confirmed, waitlist offer and "cinema awaiting approval" are sent by the API through Expo Push when they happen | No cron (Hobby crons run once a day) |
| Scanner | `expo-camera` barcode scanning → `POST /checkin`; `expo-haptics` | Reuses the v1 endpoint (B10) |
| Build | EAS Build (free tier): Android APK linked from landing + README; iOS via Expo Go link | No store accounts needed for a portfolio |
| Tests | One Jest test for the SVG hit-test (tap point → seat id); everything else is API-tested already | Lean |

Deep links: `frontrow://book/{showtimeId}`, `frontrow://tickets/{orderId}`; universal links on `frontrow.virajdomadia.com/app/*` later if hours remain.

## 13. Environment
`api/`: `DATABASE_URL`, `REDIS_URL`, `SESSION_SECRET`, `TICKET_SECRET`, `WEB_URL`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `EMAIL_FROM`, `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET`, optional `BLOB_READ_WRITE_TOKEN`. `web/`: `API_URL`, `NEXT_PUBLIC_RAZORPAY_KEY_ID`. v4 `mobile/`: `EXPO_PUBLIC_API_URL`, `EXPO_PUBLIC_RAZORPAY_KEY_ID`; `api/`: `EXPO_ACCESS_TOKEN`.
