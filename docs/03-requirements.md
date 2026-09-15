# Frontrow — Requirements & Scope

**Lifecycle step:** 3 of 17 · **Locked:** 2026-09-15 · **Source:** [PRD.md](../PRD.md) locked decisions. Flows and screen index: [03-user-flows.md](03-user-flows.md).

Actors: **Customer** (books), **Organiser** (runs venues/events), **Visitor** (not signed in). Each requirement ends with **Accept:** — the check that closes it. Ids: R = v1, R2 = v2, R3 = v3.

---

## v1 — Box office (base, ≈ 18 h)

### R1. Browse events
- `/events` lists live events with poster, title, type (movie/concert), genre, rating/duration, "from ₹" price, next showtime. Filters: date (today / tomorrow / this weekend / pick a date), type, genre, venue; sort by soonest / price. Filters live in the URL.
- Landing page (already live) gets a real "Now showing" strip fed from the same query.
- **Accept:** every seeded event appears; a filter URL renders server-side with the right subset; empty state when nothing matches.

### R2. Event page & showtimes
- `/events/[slug]`: hero (poster/backdrop), synopsis, cast/line-up, duration, genre, rating, gallery; showtimes grouped by day then venue, each showing tier prices and a fill indicator (Available / Filling fast ≥ 70 % held+sold / Sold out).
- **Accept:** past showtimes hidden; sold-out showtimes visible but disabled; JSON-LD `Event` present.

### R3. Seat map
- `/book/[showtimeId]`: SVG map generated from the venue's layout JSON — sections, rows, seat numbers, screen/stage marker, tier legend with prices. Seat states: available (tier colour), **held by someone else** (grey), **sold** (dark), **mine** (accent, with countdown). Hover/tap shows row-seat and price. Arena template: section overview → tap a section → zoomed seat view; pan/zoom on touch and wheel.
- Max 10 seats per order; running total in a sticky footer with a **Proceed** button.
- Keyboard: arrow keys move between seats, Enter toggles. A visually-hidden list of selected seats for screen readers.
- Seat state refreshes every 5 s from `GET /showtimes/{id}/seats` (v2 swaps this for SSE).
- **Accept:** all three templates render correctly at 390 px and 1440 px; a seat that is held/sold cannot be selected; the map never shows a seat as available that the API says is not.

### R4. Holds
- Tapping seats calls `POST /showtimes/{id}/holds` with the whole current selection; the API grants all or none (Lua, `SET NX EX 600`). On conflict the map shows a toast "Seat F7 was just taken", drops that seat, and keeps the rest.
- A 10-minute countdown starts at the first successful hold; it is shown on the map, the checkout page and the tab title. Deselecting a seat releases just that hold. Leaving the page keeps holds (they expire on their own).
- Holds belong to a **session id** (cookie) so a visitor can hold before signing in; signing in at checkout adopts the holds.
- **Accept:** test — two parallel requests for the same seat: exactly one 200, one 409 naming the seat. Test — hold expires after TTL and the seat is available again. A hold never outlives its TTL by more than 1 s.

### R5. Checkout & payment
- `/checkout/[orderId]`: seats, tiers, subtotal, convenience fee (flat ₹30/ticket, shown honestly), total; countdown continues. Sign in / sign up inline if a visitor.
- `POST /orders` verifies every seat is held by this session, creates a Razorpay order, returns the checkout params. Razorpay Checkout modal (test mode). On success the page polls the order until the webhook confirms; after 20 s without confirmation it shows "Payment received, confirming…" and keeps polling.
- Webhook `payment.captured`: verify signature, dedupe by Razorpay event id, then one DB transaction inserts tickets (`UNIQUE (showtime_id, seat_id)`), marks the order paid, deletes the Redis holds, bumps the version counter.
- **Paid after expiry:** if the holds are gone but the seats are still free → sell; if any seat is sold to someone else → refund the whole payment via Razorpay, order → `refunded`, customer sees why.
- Orders with no payment 15 min after creation → `expired` (checked lazily on read; no cron).
- **Accept:** test — webhook replay is a no-op; test — forged signature rejected; test — paid-after-expiry both branches; total = Σ tier price + fee.

### R6. Tickets
- `/tickets/[ticketId]`: event, venue, showtime, seat(s), QR code encoding a signed token (`ticket_id.exp.sig`), "Add to calendar" link. One ticket row per seat; one page per order listing all its tickets.
- `/my-tickets`: upcoming and past, grouped by showtime.
- **Accept:** the QR decodes to a token the API verifies; another user's ticket URL → 404.

### R7. Auth
- Email + password, cookie session, roles `customer` | `organiser`. Sign up, sign in, sign out, forgot-password (email link, v2 when Resend lands — v1 shows "contact us"). Demo logins on the landing page.
- **Accept:** protected routes redirect to sign in and back; organiser routes 403 for customers.

### R8. Organiser console
- `/organiser`: venues, events, showtimes, bookings.
- **Venues:** create from a template (grid / stalls+balcony / arena) with name, address, and per-template knobs (rows × seats for grid; section count for arena). Seats are generated and stored as rows.
- **Events:** create/edit title, type, genre, duration, rating, synopsis, cast, poster + gallery (URL fields in v1; upload is v2), status draft/live.
- **Showtimes:** pick event + venue + start time + price per tier; status scheduled/cancelled. Cancelling a showtime with sold tickets is blocked in v1.
- **Bookings:** per showtime, list of paid orders (customer, seats, amount, time); CSV export.
- **Accept:** a new organiser can go from sign-up to a bookable showtime in under 3 minutes; the seeded organiser sees only their own venues/events.

### R9. Seed & content
- Seed script (idempotent): platform + demo organiser + demo customer, 3 venues, ~8 events with CC photos and credits file, ~20 showtimes over the next 14 days (regenerated relative to "now" so the demo never goes stale), a scatter of sold seats per showtime so maps don't look empty.
- **Accept:** `seed` runs twice without duplicates; every showtime has at least one sold and one available seat.

---

## v2 — Live hall (mid, ≈ 10 h)

### R2-1. Realtime seat state
- `GET /showtimes/{id}/stream` (SSE): initial snapshot, then diffs whenever the version counter changes and at each known hold expiry. Server loop reconnects cleanly at Vercel's function limit; the client's `EventSource` resumes with `Last-Event-ID`.
- Client swaps polling for the stream; falls back to 5 s polling if SSE fails twice.
- **Accept:** in two tabs, a hold/release/sale is visible in the other tab within 1 s (measured in an e2e test with a 1.5 s tolerance).

### R2-2. Live sales dashboard
- `/organiser/dashboard`: today's revenue, tickets sold, occupancy per upcoming showtime (sold / held / free), a live mini seat map per showtime, last 20 orders — updated over the same SSE stream.
- **Accept:** a purchase in another tab updates the numbers without reload.

### R2-3. Check-in
- `/checkin/[showtimeId]` (organiser): paste/scan a ticket token (camera via the browser's BarcodeDetector where available, text field otherwise) → valid / already used / wrong showtime; marks `checked_in_at` once.
- **Accept:** second scan of the same ticket says "already checked in at HH:MM".

### R2-4. Email
- Ticket email on payment (Resend, React Email template with the QR); forgot-password link.
- **Accept:** email arrives in test inbox with a working ticket link.

### R2-5. Poster upload
- Organiser uploads poster/gallery images (Vercel Blob) instead of URLs.

---

## v3 — Full house (advanced, ≈ 10 h)

### R3-1. Waitlist
- Sold-out showtime → "Join waitlist" (seat count, max price). When a hold lapses or an order is refunded, the first matching waitlist entry gets a 10-min exclusive hold and an email/push; unclaimed → next in line.
- **Accept:** test — lapse → offer → claim flow; offers never double-hold.

### R3-2. Best available
- "Pick for me": choose N seats together, closest to centre, within a tier; preview then hold.
- **Accept:** returns contiguous seats when they exist; explains when it can't.

### R3-3. Dynamic pricing
- Organiser enables per showtime: tier price rises by X % at 50 % / 75 % / 90 % occupancy; the map shows the current price and "price rises at 75 %".
- **Accept:** price shown = price charged, computed server-side at hold time and frozen for the hold.

### R3-4. Seat-view preview
- Hovering a section (arena/auditorium) shows a photo "view from here" (CC photos per section).

### R3-5. Ticket transfer
- Owner enters a friend's email → the friend gets a claim link; the QR token rotates so the old one is void.
- **Accept:** old QR rejected at check-in after transfer.

### R3-6. Seat heatmap
- Organiser: per venue, which seats sell first across showtimes (colour scale on the map).

---

## Out of scope (all versions)
Custom layout editor · refunds UI · native scanner app · real money · multi-city · GA/standing zones · promo codes · full WCAG on the SVG map (keyboard + SR list only) · reserved-seat pricing per seat (tiers only).
