# Frontrow — Development Plan

**Lifecycle step:** 7 of 17 · **Re-planned:** 2026-11-15/16 (movies only, three roles) · **Total:** ~70.25 h over 33 rows (v4 +2 h for multi-scanner offline check-in, Viraj, 2026-11-19) · **Inputs:** [03-requirements.md](03-requirements.md), [04-technical-design.md](04-technical-design.md), [06-data-and-api.md](06-data-and-api.md).
**Tracker:** https://claude.ai/artifact/SYCP9jsFMK9fgkoyCyq8DA — the same rows with live status, updated per milestone.

**How to read it:** each version is split by role. Row numbers give the build order inside a version (B1 → B11, L1 → L8, A1 → A6, M1 → M7). Every row is one branch and one PR, squash-merged, starts in a new chat, and ships something visible.
**Already built (reused):** S1 brand + tokens (PR #2, #4) · S2 API, database, seed (#11) · S3 shows pages (#12) · F1 seat map (#13). B1 reworks them from events into films, cinemas and screens.
**Lean rules:** plain CI only (web typecheck + build, api ruff + pytest); tests only where a demo bug would embarrass; accounts and keys in the row that first needs them (Upstash + Gmail in B2, Razorpay in B6, Expo/EAS in M1); free tiers only; no browser storage.

---

## v1 — Box office (≈ 26.0 h)

Movies only, in Bengaluru. The full loop for all three roles: a customer books on a phone and is scanned in at the door; a theatre owner sets up screens and schedules shows; staff run the film catalogue and approvals. Rows are grouped by role; numbers give the build order. About 7 h already built (brand, API + database, shows pages, seat map) is reused inside B1 and B3–B5.

### All roles · foundation (≈ 6.0 h)
Films, cinemas and screens replace events; the new look; a catalogue that never empties; three sign-in doors on email codes with demo buttons.

| # | Part | web/ (or mobile/) | api/ | Est. | Done when |
|---|---|---|---|---|---|
| B1 | **Films, cinemas, screens + fresh seed + new look** | Restyle to the chosen look: paper pages, oxblood header with the torn-stub edge (globals.css tokens; Box office style otherwise unchanged). Rewrite the landing page for movies (no concert copy). Home and movie pages read films; cinema and screen names on showtimes. Arena template dropped. Reuses what is built: S1 brand, S2 API + database, S3 shows pages. | Rework events → shared films catalogue (title, poster, synopsis, cast, runtime, certificate, genres, languages, formats, trailer link, release date, status); businesses → cinemas → screens (layout from grid / stalls+balcony, tiers, formats); shows = film + language + format + screen + time + tier prices. Seed: 3 cinema businesses, 8 fictional films with CC photos, repeating schedules materialised lazily so the next 14 days always exist (no cron). | 3.5 h | Prod is paper + oxblood, the landing talks about movies, and home lists films today and still does a month later without a reseed. |
| B2 | **Sign-in: email code, three doors** | Customer /sign-in (email → 6-digit code → name if new; also mid-booking), business door /business (register + sign-in), hidden staff door /staff. Landing demo buttons: customer, theatre owner, staff. Account page. | Upstash Redis created here (codes, rate limits; later holds). Code hashed in Redis, 10-min TTL, 5 tries, per-email + per-IP limits; staff door answers the same for any email. Gmail SMTP from a Frontrow Gmail (ported from Tripsmith). One email = one person; business membership and staff flag on top; 30-day cookie session; bearer tokens for v4. Tests: access rules, code expiry/tries, rate limit. | 2.5 h | Each demo signs in with one click; a real email gets a code; access tests green. |

### Customer (≈ 10.25 h)
BookMyShow's flow: home, movie, language/format, showtimes, how many seats, seat map with holds, summary, Razorpay, M-ticket.

| # | Part | web/ (or mobile/) | api/ | Est. | Done when |
|---|---|---|---|---|---|
| B3 | **Home, search, movie page** | Home: Now showing + search box. Movie page: poster, banner, synopsis, cast and crew, certificate, runtime, trailer link, Book tickets. | GET /home, /films?q=, /films/{slug}; cached s-maxage=60. | 1.5 h | Search finds a film by title; movie page renders at 390 and 1440 px. |
| B4 | **Language/format + showtimes** | Language and format picker (e.g. Hindi · 2D) when a film has more than one; showtimes page with a date strip, cinemas list, times coloured by availability, sold out greyed. | GET /films/{slug}/shows?date=&lang=&format= grouped by cinema; fill from sold + held. | 1.5 h | Times show the right colour for available / filling fast / sold out. |
| B5 | **How many seats + seat map + 10-minute holds** | Certificate notice before seats when needed (e.g. 'A: 18+ only, ID may be checked'). Then 'How many seats?' (1–10) before the map; tapping a seat picks that many together; seats held 10 minutes, grey for others (5 s poll); countdown in page and tab title; 'F7 was just taken'; 'seats released, pick again'. | Lua all-or-none holds in Redis + version counter; sold set cached in Redis, version-gated poll so Neon stays asleep; fr_sid cookie adopted on sign-in. Tests: 20-way race → one winner; all-or-none; expiry frees seats. Reuses the F1 seat map (core.ts, SVG renderer); its arena code goes. | 3.25 h | Two tabs can never hold the same seat; hold tests green in CI. |
| B6 | **Summary + Razorpay** | Summary with ticket price and convenience fee shown separately, demo test-card note, Pay; Razorpay test mode; confirming state; failed payment keeps seats held; paid-too-late refund page. | Razorpay test account + webhook created here. Orders with server totals; verify fast path; webhook HMAC + dedupe; confirm transaction with UNIQUE(show, seat); paid after expiry: free → sell, sold → refund. Tests: signature, replay, both refund branches, totals. | 2.5 h | Test payment produces tickets; webhook replay does nothing. |
| B7 | **M-ticket + email + my tickets** | Ticket page: QR per seat, booking ID, receipt, add to calendar, tear-off motion. My tickets upcoming / past. Confirmation email with the ticket link. | Signed ticket token per seat; owner-only ticket pages (others → 404); email via the B2 sender. | 1.5 h | QR decodes to a token the API verifies; email arrives. |

### Theatre owner (≈ 7.0 h)
Register, cinemas, screens, pick films, bulk shows, bookings, scan at the door.

| # | Part | web/ (or mobile/) | api/ | Est. | Done when |
|---|---|---|---|---|---|
| B8 | **Owner: register, cinemas, screens** | Business registration (account → business details) with Pending verification; add cinemas (address, facilities); add screens from a layout template with live preview, tiers and formats. | Businesses, cinemas, screens CRUD scoped to the owner (other business → 404). | 3 h | A new owner sets up a cinema with two screens in under 3 minutes. |
| B9 | **Owner: films, bulk shows, bookings** | Pick a film from the catalogue, or request a missing one (staff handle it in B11); bulk-schedule: language + format + screen + days + times + tier prices; overlap warning; publish; bookings list per show + CSV. | Bulk show creation with overlap check (runtime + cleaning gap); public only when the business is verified. | 2.5 h | Scheduled shows appear on the film's page under that cinema after approval. |
| B10 | **Scan at the door** | Check-in page for ushers: phone camera (BarcodeDetector) or paste; Valid / Already checked in HH:MM / Wrong show / Not a ticket. Customer's ticket shows Checked in. | POST /checkin single-use update; show + cinema match. | 1.5 h | Second scan says 'already checked in'. |

### Frontrow staff (≈ 2.75 h)
Film catalogue, film requests, cinema approvals. v1 tagged.

| # | Part | web/ (or mobile/) | api/ | Est. | Done when |
|---|---|---|---|---|---|
| B11 | **Staff: film catalogue, film requests, approvals** | Hidden staff area: add / edit films with all details and status (coming soon / now showing / ended); film requests from owners (add the film, or decline with a reason); approvals queue for new businesses with Approve / Reject + reason. Demo staff view-only. v1 close: README section on how holds work. | Staff-only routes; approval flips public listing on. | 2.75 h | A new owner's shows go public after approval; v1 tagged. |

---

## v2 — Live hall (≈ 13.75 h)

Seats change live for everyone and the landing page shows it side by side; a cinema runs its whole day on Frontrow (today board with live sales, blocked seats, counter sales, cancel a show); staff get cinema suspension, support and the marketplace view. Live updates push only on change to stay inside the free tiers.

### Customer (≈ 4.5 h)
Seats change live for everyone; the landing page shows it side by side.

| # | Part | web/ (or mobile/) | api/ | Est. | Done when |
|---|---|---|---|---|---|
| L1 | **Live seat updates** | Seat map updates live without refresh; falls back to polling; ripple when someone else takes a seat. | Server push only on change (no 1/s polling) so Upstash, Vercel and Neon stay inside free limits; design settled at the start of the row. | 3 h | Two tabs: a hold shows in the other in under a second. |
| L2 | **'Try it live' on the landing page** | Two mini seat maps of one show side by side, driven by the real updates. | — | 1.5 h | The wow works without opening two tabs. |

### Theatre owner (≈ 6.0 h)
Today board with live sales and blocked seats, counter sales, cancel a show.

| # | Part | web/ (or mobile/) | api/ | Est. | Done when |
|---|---|---|---|---|---|
| L3 | **Today board + live sales + block seats** | Every show today with fill and a live seat map, plus today's revenue, tickets sold and recent orders updating live; block seats (broken, staff, guests). | Blocked seats stored per show; counted as unavailable. | 2.5 h | A purchase in another tab updates the board; blocked seats can't be booked online. |
| L4 | **Counter sales** | Cashier taps seats on the same live map and marks them paid in cash; prints nothing, shows a QR to scan. | Counter orders without Razorpay; same UNIQUE guard. | 2 h | Online and counter can never sell the same seat. |
| L5 | **Cancel a show** | Owner cancels a show with a reason; every buyer is refunded and emailed; the show disappears. | Razorpay refunds per order; idempotent. | 1.5 h | All test orders refunded once, emails sent. |

### Frontrow staff (≈ 3.25 h)
Cinema list + suspend, customer support, marketplace view.

| # | Part | web/ (or mobile/) | api/ | Est. | Done when |
|---|---|---|---|---|---|
| L6 | **Staff: cinema list + suspend** | Every business and its cinemas with status; suspend a cinema (hides its shows, existing tickets unaffected). | — | 0.75 h | A suspended cinema's shows disappear; its ticket holders still get in. |
| L7 | **Staff: customer support** | Find a booking by ID or email; see seats, payment, scan status; resend ticket email; refund. | Staff support routes, audited. | 1.5 h | A booking can be found and refunded in under a minute. |
| L8 | **Staff: marketplace view** | Tickets sold, total sales, Frontrow fee, busiest films and cinemas (today / week / month). | Aggregates; cached. | 1 h | Numbers match seeded + test orders. |

---

## v3 — Full house (≈ 10.0 h)

Reviews after scan-in, waitlist for sold-out shows, sales reports, payouts, seat heatmap and review moderation.

### Customer (≈ 5 h)
Reviews after scan-in; waitlist for sold-out shows.

| # | Part | web/ (or mobile/) | api/ | Est. | Done when |
|---|---|---|---|---|---|
| A1 | **Reviews and ratings** | After being scanned in, rate and review the film; rating % on the movie page. | Review only with a checked-in ticket. | 2 h | A customer who wasn't scanned in can't review. |
| A2 | **Waitlist** | Join a sold-out show's waitlist; when seats free up the next person gets a 10-minute exclusive hold by email. | Offer on release / refund; unclaimed → next. Test: lapse → offer → claim. | 3 h | Test green; offers never double-hold. |

### Theatre owner (≈ 4.5 h)
Sales reports, payouts, seat heatmap.

| # | Part | web/ (or mobile/) | api/ | Est. | Done when |
|---|---|---|---|---|---|
| A3 | **Sales reports** | By film, show and day, with CSV. | Report aggregates. | 1.5 h | Report totals match orders. |
| A4 | **Payouts** | Owner: weekly statement (sales − Frontrow fee). Staff: what each cinema is owed, mark as paid. Ledger only. | Payout ledger. | 2 h | Statement equals sales minus fee, to the paisa. |
| A5 | **Seat heatmap** | Which seats sell first across shows, on the seat map. | Aggregate per screen. | 1 h | Heatmap matches seeded sales. |

### Frontrow staff (≈ 0.5 h)
Review moderation (payout settling sits in A4).

| # | Part | web/ (or mobile/) | api/ | Est. | Done when |
|---|---|---|---|---|---|
| A6 | **Staff: review moderation** | Remove abusive reviews with a reason. | — | 0.5 h | Removed review disappears from the movie page. |

---

## v4 — In your pocket · one app, three roles (≈ 20.5 h)

One Expo app (Android build + Expo Go). Sign in and it shows your role. Customers get the whole booking flow plus an offline wallet and push. Theatre owners and staff get the jobs done on their feet (scanner, today board, counter; approvals, support); setup, scheduling, reports and catalogue work stay on the website.

### All roles (≈ 5 h)
App shell with role tabs, push notifications, Android build.

| # | Part | web/ (or mobile/) | api/ | Est. | Done when |
|---|---|---|---|---|---|
| M1 | **App shell + sign-in + role tabs** | Expo Router; email-code sign-in; tabs by role (customer / owner / staff); brand look; generated API types. Expo + EAS accounts created here. | — (bearer tokens from B2) | 2 h | Each demo role signs in on a phone and sees its own tabs. |
| M4 | **Push notifications** | '2 minutes left on your hold' scheduled on the phone itself; confirmations, waitlist offers and staff approval alerts from the server. | Device tokens; sends on events (no cron). | 2 h | Backgrounded hold → reminder at T-2:00. |
| M7 | **Ship** | EAS Android build, Expo Go link, 'Get the app' on the landing page with QR. | — | 1 h | A reviewer installs the app in under a minute. |

### Customer (≈ 7.5 h)
Booking flow, reviews, waitlist, offline wallet.

| # | Part | web/ (or mobile/) | api/ | Est. | Done when |
|---|---|---|---|---|---|
| M2 | **Customer: browse, book, pay** | Home, search, movie, language/format, showtimes, certificate notice, how many seats, seat map over the shared seat-map core with pinch/pan, holds, Razorpay RN, ticket, review after the show, join a waitlist. | — | 5.5 h | Test payment in the app produces a ticket that scans. |
| M3 | **Offline wallet** | Tickets saved on the device, open in airplane mode, brightness up, add to calendar. | — | 2 h | Airplane mode: ticket opens and scans. |

### Theatre owner (≈ 6 h)
Door scanner (many phones, honest offline), today board with live sales, blocked seats, counter.

| # | Part | web/ (or mobile/) | api/ | Est. | Done when |
|---|---|---|---|---|---|
| M5 | **Owner: scanner, today, counter** | Door scanner with camera, haptics and running count; today board with live sales; block seats; counter sale on the phone. Setup, scheduling, reports and payouts stay on the website. | — (v1/v2 routes) | 4 h | 20 scans a minute; duplicate refused. |
| M5b | **Offline scans + sync** (Viraj, 2026-11-19) | Pre-doors scan-list download to SQLite; offline provisional accept + queue (ticket, scanner, `scanned_at`); same-phone rescan blocked; counter: confirmed · pending sync; flagged list | `checkins` table; `GET /owner/shows/{id}/scan-list` (Ed25519-signed), `POST /checkins/sync` (batch, idempotent per `client_scan_id`), reconcile by server commit order | 2 h | Two offline scans of one ticket, synced in either order → 1 `confirmed` + 1 `duplicate_flagged`, counted once (test); pending never shown as confirmed |

### Frontrow staff (≈ 2 h)
Approvals queue, booking lookup and resend.

| # | Part | web/ (or mobile/) | api/ | Est. | Done when |
|---|---|---|---|---|---|
| M6 | **Staff: approvals + support** | Approvals queue, booking lookup and resend on the phone. Catalogue editing, requests, suspend, refunds, marketplace, payouts and moderation stay on the website. | — | 2 h | Approve a cinema from the phone. |

---

## Summary

| Version | Hours | Proves |
|---|---|---|
| v1 Box office | 26.0 | The full loop for all three roles |
| v2 Live hall | 13.75 | Live seats; a cinema runs its day on Frontrow |
| v3 Full house | 10.0 | Reviews, waitlist, the money side |
| v4 In your pocket | 20.5 | One app, three roles; honest offline door scanning |
| **Total** | **70.25** | |

## Dropped on 2026-11-16 (carried from the old plan, not in the role flows)
Cinema pages and favourites · reminder email · coming soon + notify me · pick for me · view from your seat · ticket transfer · dynamic pricing · a separate live sales dashboard (folded into the today board). The old add-on bucket is retired with the old plan.
