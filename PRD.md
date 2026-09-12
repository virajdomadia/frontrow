# PRD — Frontrow: Movie/concert ticketing with live seat map

**Status:** draft v0 (basic) · to be detailed together
**Name:** Frontrow · *pick your seat, live*
**URL:** https://frontrow.virajdomadia.com
**Slot:** #2 · Budget ~35 h · Build second

## One-liner
BookMyShow-style ticketing where you pick seats on a live map, they're held for you for 10 minutes and grey out for everyone else, and you pay with Razorpay to get a QR ticket.

## Who it's for
- **Customer:** someone booking seats for a show.
- **Organiser/admin:** venue or event owner creating shows and watching sales.

## Why this project
- The seat-hold problem (two people, one seat, same second) is a classic system-design interview question — this is it, built for real.
- Very visual; immediate demo in an interview with two browser tabs.

## Core features (thin vertical slice)
**Customer**
- Events list → event page → pick showtime
- Interactive seat map (sections, rows, pricing tiers)
- Select seats → 10-min hold with countdown → Razorpay checkout → ticket with QR code
- Seat state updates live for all viewers (available / held / sold)
- My tickets page

**Admin**
- Create event, venue layout (from a template), showtimes, prices
- Sales dashboard per show

## The wow moment
Open two tabs: pick a seat in one, watch it grey out instantly in the other; let the timer expire and watch it come back.

## Out of scope (v1)
Custom venue-layout editor, refunds, ticket transfer, scanning app (a check-in page that validates the QR is enough).

## Tech notes (to discuss)
- Holds: Redis (Upstash) key with TTL per seat + DB transaction on confirm; idempotency key on payment
- Realtime: WebSocket/SSE broadcast of seat state per showtime
- Payments: Razorpay Checkout + webhook; handle "paid after hold expired" edge case
- QR: signed token, verified on a check-in page

## Success criteria
- Concurrent selection of the same seat by two users can never double-sell (covered by a test)
- Hold expiry releases seats within ~1 s for all viewers

## Open questions
- Movies vs concerts vs both for seed data?
- WebSocket server (separate Node service) vs SSE from Next.js?
