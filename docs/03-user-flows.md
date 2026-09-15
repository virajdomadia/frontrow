# Frontrow — User Flows & Screen Index

**Lifecycle step:** 3 of 17 · **Locked:** 2026-09-15 · Pairs with [03-requirements.md](03-requirements.md); every screen below gets a mockup in [04-ui-mockups.md](04-ui-mockups.md).

## Flow 1 — Book seats (v1, the main path)

```mermaid
flowchart LR
  L[S1 Landing] --> E[S2 Events list]
  E --> D[S3 Event page]
  D -->|pick showtime| M[S4 Seat map]
  M -->|tap seats| H{POST holds}
  H -->|all granted| M2[Seats mine · 10:00 countdown]
  H -->|409 taken| T[Toast: seat taken] --> M
  M2 -->|Proceed| C[S5 Checkout]
  C -->|visitor| A[S9 Sign in / up] --> C
  C -->|Pay| R[Razorpay modal]
  R -->|success| W[Confirming… polls order]
  W -->|webhook paid| K[S6 Ticket with QR]
  W -->|refunded| X[Sorry — seat sold, refunded]
  K --> Y[S7 My tickets]
```

## Flow 2 — Hold lifecycle (v1 rules, v2 visibility)

```mermaid
stateDiagram-v2
  [*] --> Available
  Available --> Held: POST holds (Lua all-or-none)
  Held --> Available: TTL 600 s expires · or deselect · or order refunded
  Held --> Sold: webhook payment.captured (tx inserts ticket)
  Sold --> [*]
  note right of Held
    Redis hold:{showtime}:{seat} = session
    every change INCR st:{showtime}:v
    v1: viewers poll /seats every 5 s
    v2: SSE stream pushes within 1 s
  end note
```

## Flow 3 — Paid after hold expired (v1)

```mermaid
flowchart TD
  W[Webhook payment.captured] --> V{signature ok · event id new?}
  V -->|no| N[200 no-op]
  V -->|yes| Hq{holds still ours?}
  Hq -->|yes| S[Insert tickets · order paid · DEL holds · INCR v]
  Hq -->|no| F{seats still free in DB?}
  F -->|yes| S
  F -->|no| Rf[Razorpay refund · order refunded · email why]
```

## Flow 4 — Organiser creates a bookable show (v1)

```mermaid
flowchart LR
  O[S9 Sign up as organiser] --> V[S10 Venues: new from template]
  V --> Ev[S11 Events: new]
  Ev --> St[S12 Showtimes: event + venue + time + tier prices]
  St --> Live[Showtime live on S2/S3]
  Live --> B[S13 Bookings list]
```

## Flow 5 — Live hall (v2)

```mermaid
sequenceDiagram
  participant A as Tab A
  participant API as FastAPI /stream
  participant R as Redis
  participant B as Tab B
  B->>API: GET /showtimes/7/stream (SSE)
  API-->>B: snapshot {sold, held, expiries}
  A->>API: POST /holds [F7]
  API->>R: Lua SET NX EX · INCR v
  loop every 1 s or at next expiry
    API->>R: GET st:7:v
  end
  API-->>B: diff {held:+F7, expires_at}
  Note over B: F7 greys out < 1 s
  Note over API,R: at expires_at: re-read, push {held:-F7}
```

## Flow 6 — Check-in (v2) and Waitlist (v3)

```mermaid
flowchart LR
  subgraph v2 check-in
    Q[S15 Check-in: scan/paste token] --> Vt{verify sig · showtime · unused}
    Vt -->|ok| OK[Valid ✓ · mark checked_in_at]
    Vt -->|used| U[Already checked in HH:MM]
    Vt -->|bad| Bad[Invalid]
  end
  subgraph v3 waitlist
    SO[S4 sold out] --> J[Join waitlist: seats, max price]
    Lapse[hold lapses / refund] --> Off[10-min exclusive hold + email]
    Off -->|claim| C5[S5 Checkout]
    Off -->|unclaimed| Next[next in line]
  end
```

## Screen index

| # | Screen | Route | Who | Version | Notes |
|---|---|---|---|---|---|
| S1 | Landing | `/` | visitor | v1 | Exists; gains real "Now showing" strip + demo logins |
| S2 | Events list | `/events` | visitor | v1 | Filters in URL |
| S3 | Event page | `/events/[slug]` | visitor | v1 | Showtimes by day → venue, fill indicator |
| S4 | Seat map | `/book/[showtimeId]` | visitor/customer | v1 · live in v2 | The signature screen; 3 templates; countdown |
| S5 | Checkout | `/checkout/[orderId]` | customer | v1 | Inline sign-in; Razorpay modal; confirming state |
| S6 | Ticket | `/tickets/[orderId]` | customer | v1 | QR per seat; calendar link |
| S7 | My tickets | `/my-tickets` | customer | v1 | Upcoming / past |
| S8 | Refunded / failed order | `/checkout/[orderId]` state | customer | v1 | Paid-after-expiry explanation |
| S9 | Sign in / Sign up | `/sign-in`, `/sign-up` | all | v1 | Role picker on sign-up; demo buttons |
| S10 | Organiser · Venues | `/organiser/venues` | organiser | v1 | Template picker + knobs; layout preview |
| S11 | Organiser · Events | `/organiser/events` | organiser | v1 | Form + list |
| S12 | Organiser · Showtimes | `/organiser/showtimes` | organiser | v1 | Tier prices; cancel guard |
| S13 | Organiser · Bookings | `/organiser/bookings/[showtimeId]` | organiser | v1 | Paid orders; CSV |
| S14 | Organiser · Dashboard | `/organiser/dashboard` | organiser | v2 | Live revenue/occupancy, mini maps |
| S15 | Check-in | `/checkin/[showtimeId]` | organiser | v2 | Camera or paste |
| S16 | Waitlist join + offer | `/book/[showtimeId]` state · email link | customer | v3 | |
| S17 | Transfer ticket | `/tickets/[orderId]` action · claim page | customer | v3 | |
| S18 | Organiser · Heatmap | `/organiser/venues/[id]/heatmap` | organiser | v3 | |
