# Frontrow — Database + API Design

**Lifecycle step:** 6 of 17 · **Re-planned:** 2026-11-15/16 (movies only, three roles) · Behaviour in [04-technical-design.md](04-technical-design.md).
The tables built in S2 (`events`, `venues`, `showtimes`, organiser `users.role`) are reworked into the model below in row **B1** (a new Alembic migration). Seats, layouts, orders, tickets and the hold engine carry over.

## A. Postgres schema (v1)

```sql
create type cert            as enum ('U','UA','A');
create type film_status     as enum ('coming_soon','now_showing','ended');
create type business_status as enum ('pending','verified','rejected','suspended');
create type layout_template as enum ('grid','stalls_balcony');
create type show_status     as enum ('scheduled','cancelled');
create type order_status    as enum ('pending','paid','expired','refunded','failed');
create type order_channel   as enum ('online','counter');            -- counter: v2
create type request_status  as enum ('open','added','declined');

users        (id uuid pk, email citext unique, name text, is_staff bool default false, created_at)
sessions     (id text pk, user_id uuid fk, sid text, kind text check (kind in ('web','mobile')),
              expires_at timestamptz, created_at)                     -- sid = the anonymous fr_sid adopted
-- sign-in codes live in Redis (B), not Postgres

businesses   (id uuid pk, name, slug unique, phone, logo_url, status business_status,
              review_note text, created_at, verified_at)
business_members (business_id uuid fk, user_id uuid fk, role text default 'owner',   -- 'usher' later
              primary key (business_id, user_id))

films        (id uuid pk, slug unique, title, synopsis, cast_crew jsonb, runtime_min int, cert cert,
              genres text[], languages text[], formats text[], poster_url, banner_url, trailer_url,
              release_date date, status film_status, created_by uuid fk users, created_at)
film_requests (id uuid pk, business_id uuid fk, title text, note text, status request_status,
              film_id uuid fk null, reply text, created_at)

cinemas      (id uuid pk, business_id uuid fk, name, area, address, facilities text[], created_at)
screens      (id uuid pk, cinema_id uuid fk, name, template layout_template, knobs jsonb, layout jsonb,
              tiers jsonb,                                            -- [{key,label}] in price order
              formats text[], seat_count int)
seats        (id uuid pk, screen_id uuid fk, section_key, row_label, number int, tier_key, x int, y int)
              unique (screen_id, section_key, row_label, number)

show_schedules (id uuid pk, screen_id uuid fk, film_id uuid fk, language, format,
              days_of_week int[], times time[], from_date date, to_date date,
              prices jsonb)                                           -- {tier_key: paise}; seed + bulk scheduling
shows        (id uuid pk, schedule_id uuid fk null, screen_id uuid fk, film_id uuid fk, language, format,
              starts_at timestamptz, ends_at timestamptz, status show_status, cancel_reason text)
              index (film_id, starts_at) · index (screen_id, starts_at)
              -- no overlap per screen: exclusion constraint on tstzrange(starts_at, ends_at + cleaning gap)
show_prices  (show_id uuid fk, tier_key, price_paise int, primary key (show_id, tier_key))

orders       (id uuid pk, user_id uuid fk null, sid text, show_id uuid fk, channel order_channel,
              status order_status, subtotal_paise int, fee_paise int, total_paise int,
              razorpay_order_id unique null, razorpay_payment_id, refund_id, refund_reason, created_at, paid_at)
order_seats  (order_id uuid fk, seat_id uuid fk, tier_key, price_paise int, primary key (order_id, seat_id))
tickets      (id uuid pk, order_id uuid fk, show_id uuid fk, seat_id uuid fk, user_id uuid fk null,
              checked_in_at timestamptz null, created_at)
              **unique (show_id, seat_id)**
webhook_events (id text pk, received_at)
```
Money is integer paise. Shows are generated lazily from `show_schedules` so the next 14 days always exist (no cron); shows with orders are never regenerated. Public lists show only `verified` businesses and `now_showing` films.

**v2:** `blocked_seats (show_id, seat_id, reason, primary key (show_id, seat_id))`; `orders.channel = 'counter'`; `businesses.status = 'suspended'`.
**v3:** `reviews (id, film_id, user_id, ticket_id unique, rating int 1–5, body, removed_reason null, created_at)`; `waitlist (id, show_id, user_id, seats int, status, offered_until, created_at)`; `payouts (id, business_id, week_start date, sales_paise, fee_paise, owed_paise, paid_at null)`.
**v4:** `device_tokens (id, user_id, expo_token unique, platform, created_at, last_seen_at)`.

## B. Redis keys
| Key | Type | TTL | Written by |
|---|---|---|---|
| `otp:{email}` | hash: code hash, tries | 600 s | sign-in |
| `rl:otp:{email}` · `rl:otp:ip:{ip}` | int | 60 s / 3600 s | sign-in limits |
| `hold:{show}:{seat}` | string = sid | 600 s | acquire Lua |
| `holds:{show}` | hash seat → `sid\|expires_epoch` | none (lazy cleanup) | acquire / release / confirm |
| `sold:{show}` | set of seat ids | none | refreshed on confirm, counter sale, refund |
| `st:{show}:v` | int | none | every change |
| `rl:holds:{sid}` | int | 60 s | 30 hold calls / minute |

## C. REST API (`/api/*` from the browser; FastAPI serves `/docs`)
Error envelope: `{ "error": { "code", "message", "details" } }`. 🔒 signed in · 🎬 member of the business that owns the resource (other business → 404) · 🛠 staff · ⚙ server-to-server.

### Public
| Method | Path | Returns |
|---|---|---|
| GET | `/home` | Now showing film cards |
| GET | `/films?q=&status=` | film cards (search by title) |
| GET | `/films/{slug}` | film detail (+ rating from v3) |
| GET | `/films/{slug}/shows?date=&language=&format=` | cinemas → shows with availability (available / filling / sold_out) |
| GET | `/shows/{id}` | show detail: film, cinema, screen, tiers with prices, cert, fee |
| GET | `/screens/{id}/layout` | `Layout` JSON (cached) |
| GET | `/shows/{id}/seats?v=` | `SeatState`, or `{unchanged:true}` when `v` matches |

### Sign-in
| Method | Path | Notes |
|---|---|---|
| POST | `/auth/code` | `{ email, door: customer \| business \| staff }` → 204 (same answer for unknown staff emails) |
| POST | `/auth/verify` | `{ email, code, name?, business? }` → `Me`; adopts `fr_sid` holds |
| POST | `/auth/demo` | `{ as: customer \| owner \| staff }` → `Me` |
| POST | `/auth/sign-out` · GET `/auth/me` | |
| POST / DELETE | `/auth/token` | bearer tokens for the v4 app (same code flow) |

### Holds, orders, tickets
| Method | Path | Notes |
|---|---|---|
| POST | `/shows/{id}/holds` | `{ seat_ids[] }` → `{ expires_at }` · 409 `seat_taken {taken[]}` · 422 > 10 |
| DELETE | `/shows/{id}/holds` | `{ seat_ids[] }` |
| POST 🔒 | `/orders` | server totals; Razorpay order |
| GET 🔒 | `/orders/{id}` · POST `/orders/{id}/verify` | |
| GET 🔒 | `/my/tickets` · `/tickets/{order_id}` | QR token per seat; 404 if not owner |
| POST ⚙ | `/webhooks/razorpay` | HMAC, dedupe, confirm / refund |

### Theatre owner 🎬
| Method | Path | Notes |
|---|---|---|
| GET/POST/PATCH | `/owner/cinemas` · `/owner/cinemas/{id}/screens` | screen POST generates layout + seats |
| GET | `/owner/films` · POST `/owner/film-requests` | catalogue picker; request a missing film |
| POST | `/owner/shows/bulk` | `{ screen_id, film_id, language, format, days[], times[], from, to, prices }` → created shows or 409 `overlap {show}` |
| GET | `/owner/shows?date=` · `/owner/shows/{id}/bookings?format=json\|csv` | |
| POST | `/checkin` | `{ token, show_id }` → `valid \| used \| wrong_show \| invalid` |
| v2 | `GET /owner/today` · `POST/DELETE /owner/shows/{id}/blocks` · `POST /owner/shows/{id}/counter-orders` · `POST /owner/shows/{id}/cancel` | |
| v3 | `GET /owner/reports` · `GET /owner/payouts` · `GET /owner/screens/{id}/heatmap` | |

### Frontrow staff 🛠
| Method | Path | Notes |
|---|---|---|
| GET/POST/PATCH | `/staff/films` | catalogue |
| GET/PATCH | `/staff/film-requests` | add (links the new film) or decline with a reason |
| GET/PATCH | `/staff/businesses?status=` | approve / reject (v1), suspend (v2) |
| v2 | `GET /staff/bookings?q=` · `POST /staff/orders/{id}/resend` · `POST /staff/orders/{id}/refund` · `GET /staff/marketplace` | |
| v3 | `GET/PATCH /staff/payouts` · `GET/PATCH /staff/reviews` | |

### v3 customer · v4 app
`POST /films/{slug}/reviews` (checked-in ticket required) · `POST /shows/{id}/waitlist` · `POST /waitlist/{id}/claim` · `POST /devices` 🔒.

## D. Payload shapes that matter
```ts
type SeatState = { v: number; server_time: string; sold: string[]; held: { seat_id: string; expires_at: string }[]; mine: string[]; blocked?: string[] };
type Layout    = { template: 'grid'|'stalls_balcony'; width: number; height: number;
                   stage: { label: string; x: number; y: number; w: number };
                   sections: { key: string; label: string; tier: string; rows: { label: string; seats: { id: string; n: number; x: number; y: number }[] }[] }[] };
```
