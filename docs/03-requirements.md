# Frontrow — Requirements & Scope

**Lifecycle step:** 3 of 17 · **Re-planned:** 2026-11-15/16 (movies only, three roles) · **Source:** [PRD.md](../PRD.md). Flows and screen index: [03-user-flows.md](03-user-flows.md). Plan rows: [07-plan.md](07-plan.md).

Roles: **Customer**, **Theatre owner** (a business with one or more cinemas), **Frontrow staff**, and **Visitor** (not signed in). Each requirement ends with **Accept:** — the check that closes it. Row ids in brackets point at [07-plan.md](07-plan.md).

---

## v1 — Box office

### Everyone
**R1. Sign-in by email code** [B2]
- Three doors: `/sign-in` (customers; also opens mid-booking), `/business` (register a business or sign in to one), `/staff` (hidden; seeded staff accounts only).
- Email → 6-digit code (10-minute life, 5 tries) → signed in for 30 days. A new email at the customer door is asked for a name; at the business door, for business details.
- Limits: 1 code a minute and 5 an hour per email, plus a per-network limit. The staff door answers the same whether or not the email is staff.
- One email = one person: every account can book; business access and the staff flag are added on top.
- Landing demo buttons: Customer, Theatre owner (Orbit Cinemas), Frontrow staff — no email. Demo staff can view, not decide; demo accounts never change real data.
- **Accept:** each demo signs in with one click; a real email receives a code; access tests pass (another business's id → 404, customer → owner or staff pages refused).

**R2. Look and catalogue that never empties** [B1]
- Paper pages, oxblood header with the torn-stub edge, Box office style otherwise unchanged; landing page written for movies.
- Seed: 3 cinema businesses, their cinemas and screens, 11 real films (Hindi and Hollywood, in cinemas late Nov 2026 – Jan 2027) with their real release dates and CBFC certificates and original typographic posters; shows come from repeating schedules, generated lazily so the next 14 days always exist (no cron, no manual reseed); a coming-soon film gets shows from its release date and turns now-showing that day.
- **Accept:** prod shows films on sale today and a month later without a reseed.

### Customer
**R3. Home, search, movie page** [B3]
- Home: Now showing, search by film title.
- Movie page: poster, banner, synopsis, cast and crew, certificate (U / UA 7+ / UA 13+ / UA 16+ / A, or not yet certified), runtime, genres, trailer link, Book tickets.
- **Accept:** a search finds a film by title; the page renders at 390 and 1440 px.

**R4. Language, format, showtimes** [B4]
- If a film has more than one language or format, the customer picks one (Hindi · 2D, English · IMAX).
- Showtimes: a date strip; cinemas listed with their times; each time coloured by availability (available / filling fast ≥ 70 % held + sold / sold out, greyed).
- **Accept:** colours match the seat state; past times hidden.

**R5. Seats and holds** [B5]
- Certificate notice when needed (A: “18+ only, ID may be checked”).
- “How many seats?” (1–10) before the map. Tapping a seat picks that many together where possible.
- Seats are held for 10 minutes and grey for everyone else; a countdown shows on the page and the tab title. If two people tap the same seat, exactly one wins; the other sees “F7 was just taken” and keeps the rest. At 0:00: “Your seats were released” with Pick again.
- Holds work before sign-in and move to the account on sign-in.
- **Accept:** test — 20 parallel requests for one seat → one success; all-or-none 409 names the seat; a hold expires on time.

**R6. Summary and payment** [B6]
- Summary: seats, tier prices, convenience fee (₹30 per ticket) shown separately, total; the clock keeps running; a demo note with the test card / UPI id. No add-ons.
- Razorpay Checkout (test mode). A failed or cancelled payment keeps the seats held. Webhook confirms; deduplicated; paid after the hold expired: seats still free → sell, sold to someone else → full refund and a page explaining it.
- **Accept:** a test payment produces tickets; a webhook replay does nothing; both refund branches are tested; totals are computed on the server.

**R7. M-ticket, email, my tickets** [B7]
- Ticket page: QR per seat, booking ID, receipt (price breakdown, payment method), add to calendar, the tear-off motion. Confirmation email with the ticket link.
- My tickets: upcoming and past.
- **Accept:** the QR decodes to a token the API verifies; another person's ticket link → 404.

### Theatre owner
**R8. Register, cinemas, screens** [B8]
- Business registration (account, then business: name, phone, logo); console shows “Pending verification” until staff approve. Everything can be built while pending; nothing is public until then.
- Cinemas: name, area, address, facilities. Screens: layout template (grid, or stalls + balcony) with knobs and a live preview, tiers (Classic / Prime / Recliner…), formats (2D / 3D / IMAX).
- **Accept:** a new owner sets up a cinema with two screens in under three minutes.

**R9. Films, bulk shows, bookings** [B9]
- Pick a film from the shared catalogue, or request a missing one.
- Bulk-schedule: film + language + format + screen + days + times + a price per tier. Shows on one screen may not overlap (runtime + cleaning gap).
- Bookings per show (who, seats, amount) with CSV.
- **Accept:** scheduled shows appear on the film's page under that cinema once the business is verified; an overlap is refused with the clashing show named.

**R10. Scan at the door** [B10]
- Check-in page for ushers: phone camera or pasted code. Results: valid (name, seat), already checked in at HH:MM, wrong show, not a ticket. The customer's ticket then shows Checked in.
- **Accept:** a second scan of the same ticket is refused.

### Frontrow staff
**R11. Film catalogue, requests, approvals** [B11]
- Add and edit films (all fields in R3, plus languages, formats, release date); status coming soon → now showing → ended (ended films take no new shows).
- Film requests from owners: add the film, or decline with a reason.
- Approvals queue: new businesses with their cinemas; Approve or Reject with a reason. Approval makes their shows public.
- **Accept:** a new owner's shows go public after approval; a requested film becomes available to the owner after staff add it.

---

## v2 — Live hall
**R2-1. Live seat updates** [L1] — other people's holds, releases and sales appear in under a second without refresh; pushed only on change so the free tiers hold; falls back to polling. **Accept:** two tabs — a hold shows in the other in ≤ 1 s.
**R2-2. Try it live** [L2] — two mini seat maps of one show side by side on the landing page. **Accept:** the effect works without opening two tabs.
**R2-3. Today board, live sales, blocked seats** [L3] — every show today with fill and a live map; today's revenue, tickets and recent orders updating live; block seats (broken, staff, guests). **Accept:** a purchase in another tab updates the board; blocked seats can't be booked online.
**R2-4. Counter sales** [L4] — a cashier picks seats on the same live map and marks them paid in cash; the customer gets a QR. **Accept:** online and counter can never sell the same seat.
**R2-5. Cancel a show** [L5] — with a reason; every buyer is refunded and emailed. **Accept:** each test order refunded exactly once.
**R2-6. Cinema list and suspend** [L6] — staff see every business and cinema; suspending hides its shows, existing tickets still valid.
**R2-7. Customer support** [L7] — staff find a booking by ID or email, see seats, payment and scan status, resend the ticket, refund.
**R2-8. Marketplace view** [L8] — tickets sold, total sales, Frontrow's fee, busiest films and cinemas (today / week / month).

## v3 — Full house
**R3-1. Reviews** [A1] — only a customer who was scanned in can rate and review the film; the movie page shows the rating. **Accept:** someone not scanned in can't review.
**R3-2. Waitlist** [A2] — join a sold-out show's waitlist (number of seats); when seats free up, the next person gets a 10-minute exclusive hold by email; unclaimed → next. **Accept:** test lapse → offer → claim; offers never double-hold.
**R3-3. Sales reports** [A3] — by film, show and day, with CSV.
**R3-4. Payouts** [A4] — owner: weekly statement (sales − Frontrow fee); staff: what each cinema is owed, mark paid. Ledger only. **Accept:** statement = sales − fee, to the paisa.
**R3-5. Seat heatmap** [A5] — which seats sell first across shows, on the screen's map.
**R3-6. Review moderation** [A6] — staff remove abusive reviews with a reason.

## v4 — In your pocket (one Expo app)
**R4-1.** Email-code sign-in; tabs by role. [M1]
**R4-2. Customer:** the whole v1–v3 customer flow including reviews and joining a waitlist [M2]; offline ticket wallet with brightness and calendar [M3]; push — hold reminder at T-2:00 scheduled on the phone, booking confirmed, waitlist offer [M4].
**R4-3. Theatre owner:** door scanner (camera, haptics, count), today board with live sales, blocked seats, counter sales [M5]. Setup, scheduling, reports and payouts stay on the website.
**R4-3b. Many scanners, honest offline** (Viraj, 2026-11-19) [M5b] — any number of phones scan one show. *Online* every scan goes to `POST /checkin` (the B10 mark-used-once update): `confirmed` or "already checked in HH:MM". *Before doors* each scanner downloads the show's ticket list (`GET /owner/shows/{id}/scan-list`), signed with Ed25519 (private key on the server, public key in the app), bound to one show, versioned, expiring at show end + 2 h. *Offline* a token in the list is accepted **provisionally** (`pending_sync`), marked used on that phone (same-phone rescan blocked) and queued with ticket id, scanner id, `scanned_at`. *Reconnect:* `POST /checkins/sync` (batch, idempotent per scan id) commits scans in arrival order — first commit → `confirmed`, later scans of that ticket → `duplicate_flagged`; `scanned_at` is audit-only. The counter shows confirmed and pending sync apart, never summed; duplicates go to a flagged list. **Stated limits:** two offline scanners can each admit one ticket (flagged after sync, not prevented); a ticket refunded after the list was downloaded stays valid on that phone until it refreshes (flagged with reason `refunded`). **Accept:** (a) two devices scan one ticket online at once → one `confirmed` (API test); (b) two offline scans of one ticket synced in either order → 1 `confirmed` + 1 `duplicate_flagged`, counted once (API test); (c) N unsynced scans never change the confirmed count; (d) a tampered, expired, other-show or older-version list is refused.
**R4-4. Staff:** approvals queue, booking lookup and resend, push for a new cinema to approve [M6]. Everything else stays on the website.
**R4-5.** Android build + Expo Go, “Get the app” on the landing page [M7].

---

## Out of scope (all versions)
Concerts and events · city selection · add-ons (food, donation, offers, coupons) · customer cancellations · Google or phone sign-in · cinema pages and favourites · reminder emails · coming soon + notify · pick for me · view from your seat · ticket transfer · dynamic pricing · custom layout editor beyond the two templates · per-door ticket partitioning for scanners · real money · store listings.
