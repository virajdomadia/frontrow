# Frontrow — Database + API Design

**Lifecycle step:** 6 of 17 · **Locked:** 2026-09-15 · Behaviour in [04-technical-design.md](04-technical-design.md). Alembic `0001_v1` creates everything under **A**; v2/v3 tables get their own migrations.

## A. Postgres schema (v1)

```sql
create type user_role      as enum ('customer','organiser');
create type event_type     as enum ('movie','concert');
create type event_status   as enum ('draft','live');
create type showtime_status as enum ('scheduled','cancelled');
create type order_status   as enum ('pending','paid','expired','refunded','failed');
create type layout_template as enum ('grid','stalls_balcony','arena');

users        (id uuid pk, email citext unique, password_hash text, name text, role user_role, created_at)
sessions     (id text pk, user_id uuid fk, sid text,            -- sid = the anonymous fr_sid this session adopted
              expires_at timestamptz, created_at)   index (user_id)

venues       (id uuid pk, organiser_id uuid fk users, name, address, template layout_template,
              knobs jsonb, layout jsonb, seat_count int, created_at)   index (organiser_id)
seats        (id uuid pk, venue_id uuid fk, section_key text, row_label text, number int,
              tier_key text, x int, y int)
              unique (venue_id, section_key, row_label, number)   index (venue_id)

events       (id uuid pk, organiser_id uuid fk, slug text unique, title, type event_type, genre text,
              duration_min int, rating text, synopsis text, cast_lineup text[], poster_url, gallery_urls text[],
              status event_status, created_at)   index (status, type)
showtimes    (id uuid pk, event_id uuid fk, venue_id uuid fk, starts_at timestamptz, status showtime_status,
              created_at)   index (starts_at) · index (event_id, starts_at) · index (venue_id, starts_at)
price_tiers  (showtime_id uuid fk, tier_key text, label text, price_paise int, primary key (showtime_id, tier_key))

orders       (id uuid pk, user_id uuid fk null, sid text, showtime_id uuid fk, status order_status,
              subtotal_paise int, fee_paise int, total_paise int,
              razorpay_order_id text unique, razorpay_payment_id text, refund_id text, refund_reason text,
              created_at, paid_at)   index (user_id, created_at desc) · index (showtime_id, status)
order_seats  (order_id uuid fk, seat_id uuid fk, tier_key text, price_paise int, primary key (order_id, seat_id))
tickets      (id uuid pk, order_id uuid fk, showtime_id uuid fk, seat_id uuid fk, user_id uuid fk,
              token_version int default 1, checked_in_at timestamptz null, created_at)
              **unique (showtime_id, seat_id)** · index (user_id) · index (order_id)
webhook_events (id text pk, received_at)          -- Razorpay event id; duplicate insert = replay
```

Money is integer paise. `order_seats` freezes the price at order time (v3 dynamic pricing needs this). `tickets.token_version` lets v3 transfer rotate the QR without a new row.

**Views / helpers**
```sql
-- fill per showtime (event page badge, dashboard)
create view showtime_fill as
  select s.id showtime_id, v.seat_count, count(t.id) sold
  from showtimes s join venues v on v.id = s.venue_id
  left join tickets t on t.showtime_id = s.id group by s.id, v.seat_count;
```
Held counts come from Redis (`HLEN holds:{id}`), merged in the API.

**v2 additions:** `tickets.emailed_at`; posters move to Blob URLs (no schema change).
**v4 additions:** `sessions.kind` (`web` | `mobile`); `device_tokens (id, user_id, expo_token unique, platform, created_at, last_seen_at)`; `push_jobs (id, user_id, kind, payload jsonb, due_at, sent_at null)` index (due_at) where sent_at is null.
**v3 additions:** `waitlist (id, showtime_id, user_id, seats int, max_price_paise, status, offered_until, created_at)`; `ticket_transfers (id, ticket_id, to_email, claim_token, claimed_at)`; `showtime_pricing_rules (showtime_id, thresholds jsonb)`.

## B. Redis keys
| Key | Type | TTL | Written by |
|---|---|---|---|
| `hold:{showtime}:{seat}` | string = sid | 600 s | acquire Lua |
| `holds:{showtime}` | hash seat → `sid\|expires_epoch` | none (lazy cleanup) | acquire / release / confirm |
| `st:{showtime}:v` | int | none | every change |
| `rl:holds:{sid}` | int | 60 s | rate limit (30/min) |

## C. REST API (`/api/*` from the browser; FastAPI serves `/docs`)

Error envelope everywhere: `{ "error": { "code": "seat_taken", "message": "…", "details": {…} } }`. Auth via cookie; `🔒` = signed in, `🏟` = organiser (owner of the resource), `⚙` = server-to-server.

### Public
| Method | Path | Returns |
|---|---|---|
| GET | `/events?date=&type=&genre=&venue=&sort=` | `EventCard[]` (poster, title, type, genre, rating, duration, from_price, next_showtime) |
| GET | `/events/{slug}` | `EventDetail` + `ShowtimeSummary[]` (venue, starts_at, tiers, fill: available/filling/sold_out) |
| GET | `/venues/{id}/layout` | `Layout` JSON (cached, immutable per venue) |
| GET | `/showtimes/{id}` | `ShowtimeDetail` (event, venue, tiers, layout url) |
| GET | `/showtimes/{id}/seats` | `SeatState` `{ v, server_time, sold: seat_id[], held: {seat_id, expires_at}[], mine: seat_id[] }` |
| GET | `/showtimes/{id}/stream` | SSE — `snapshot` / `diff` / `ping` (v2) |
| GET | `/home` | landing strip: 6 `EventCard` |

### Holds & orders (session cookie `fr_sid`, signed-in optional until pay)
| Method | Path | Body → Returns |
|---|---|---|
| POST | `/showtimes/{id}/holds` | `{ seat_ids[] }` → 200 `{ expires_at, held: seat_id[] }` · 409 `seat_taken { taken: seat_id[] }` · 422 `too_many_seats` (>10) · 429 |
| DELETE | `/showtimes/{id}/holds` | `{ seat_ids[] }` → 204 |
| POST 🔒 | `/orders` | `{ showtime_id, seat_ids[] }` → 201 `{ order_id, razorpay_order_id, amount_paise, key_id, expires_at }` · 409 `hold_missing` |
| GET 🔒 | `/orders/{id}` | `Order` (status, seats, totals, tickets[] when paid, refund_reason) |
| POST 🔒 | `/orders/{id}/verify` | `{ razorpay_payment_id, razorpay_signature }` → `Order` (confirms on valid signature) |
| GET 🔒 | `/my/tickets` | `{ upcoming: TicketGroup[], past: TicketGroup[] }` grouped by order |
| GET 🔒 | `/tickets/{order_id}` | `Ticket[]` with `qr_token` each · 404 if not owner |

### Auth
| Method | Path | Body → Returns |
|---|---|---|
| POST | `/auth/sign-up` | `{ email, password, name, role }` → `Me`; adopts `fr_sid` holds |
| POST | `/auth/sign-in` | `{ email, password }` → `Me` |
| POST | `/auth/sign-out` | → 204 |
| GET | `/auth/me` | `Me { id, name, email, role }` · 401 |
| POST | `/auth/demo` | `{ as: 'customer' \| 'organiser' }` → `Me` (landing demo buttons) |

### Organiser 🏟
| Method | Path | Notes |
|---|---|---|
| GET/POST | `/organiser/venues` | POST `{ name, address, template, knobs }` → generates layout + seats |
| GET | `/organiser/venues/{id}` | venue + layout |
| GET/POST | `/organiser/events` · PATCH `/organiser/events/{id}` | fields per R8; slug from title |
| GET/POST | `/organiser/showtimes` · PATCH `/organiser/showtimes/{id}` | POST `{ event_id, venue_id, starts_at, tiers: {tier_key, label, price_paise}[] }`; PATCH cancel → 409 `has_sales` |
| GET | `/organiser/showtimes/{id}/bookings?format=json\|csv` | paid orders |
| GET | `/organiser/dashboard` (v2) | today's revenue, sold, per-showtime fill; live via the same SSE with `?organiser=1` |
| POST | `/checkin` (v2) | `{ token }` → `{ status: valid \| used \| invalid \| wrong_showtime, ticket, checked_in_at }` |

### Server-to-server ⚙
| Method | Path | Notes |
|---|---|---|
| POST | `/webhooks/razorpay` | raw body HMAC; `payment.captured` → confirm; `payment.failed` → order `failed`; always 200 after signature ok |

### v4 — mobile (sketch; detailed when v4 starts)
`POST /auth/token` `{ email, password }` → `{ token, expires_at, me }` · `DELETE /auth/token` · `POST /devices` `{ expo_token, platform }` 🔒 · `DELETE /devices/{id}` 🔒 · `POST /internal/push/due` ⚙ (Vercel Cron, `CRON_SECRET`). Every other route is unchanged; the app sends `Authorization: Bearer <token>` instead of the cookie.

### v3 (sketch; detailed when v3 starts)
`POST /showtimes/{id}/waitlist` · `POST /waitlist/{id}/claim` · `GET /showtimes/{id}/best?count=&tier=` · `POST /tickets/{id}/transfer` · `POST /transfers/{token}/claim` · `GET /organiser/venues/{id}/heatmap` · `PATCH /organiser/showtimes/{id}/pricing`.

## D. Payload shapes that matter
```ts
type SeatState = { v: number; server_time: string; sold: string[]; held: { seat_id: string; expires_at: string }[]; mine: string[] };
type SeatDiff  = { v: number; held_add?: SeatState['held']; held_del?: string[]; sold_add?: string[] };
type Layout    = { template: 'grid'|'stalls_balcony'|'arena'; width: number; height: number;
                   stage: { label: string; x: number; y: number; w: number };
                   sections: { key: string; label: string; tier: string; shape: 'rows'|'wedge'; polygon?: number[][];
                               rows: { label: string; seats: { id: string; n: number; x: number; y: number }[] }[] }[] };
```
