# PRD — Frontrow: movie ticketing with a live seat map

**Status:** v2 of the PRD · re-planned 2026-11-15/16 (movies only, three roles) · built so far: brand, API + database, shows pages, seat map (PRs #2–#13) · next: row B1
**Name:** Frontrow · *pick your seat, live*
**URL:** https://frontrow.virajdomadia.com (live at https://frontrow-viraj.vercel.app until DNS)
**Slot:** #2 · ~70 h left (v1 26 · v2 13.75 · v3 10 · v4 20.5) + ~7 h already built · plan in [docs/07-plan.md](docs/07-plan.md)
**Tracker:** https://claude.ai/artifact/SYCP9jsFMK9fgkoyCyq8DA (rows with status, docs, mockups, project data)

## One-liner
A BookMyShow-style movie ticketing marketplace for Bengaluru. Cinemas list their shows; customers pick seats on a live map where a tapped seat is held for 10 minutes and greys out for everyone else; they pay with Razorpay and walk in with a QR ticket.

## Who it's for
| Role | Who | What they do on Frontrow |
|---|---|---|
| **Customer** | Someone going to the movies | Find a film, pick a show and seats, pay, get scanned in, review it after |
| **Theatre owner** | A cinema chain or a single-screen cinema | Register, set up cinemas and screens, schedule shows from the shared film catalogue, run the day (today board, counter sales, door), see money |
| **Frontrow staff** | The company running the marketplace | Keep the film catalogue, approve cinemas, support customers, watch the marketplace, settle payouts |

## Why this project
- The seat-hold problem (two people, one seat, same second) is a classic system-design question — built here for real, with a test that proves it.
- The most visual of the four portfolio projects: the seat map is the product, and the live greying needs no explanation.

## Locked decisions
1. **Movies only.** No concerts, plays or events. Venue layouts: cinema grid, and stalls + balcony for older single screens. No arena.
2. **Bengaluru only, no city step.** Fictional films with CC photos from Wikimedia Commons (no real posters).
3. **A marketplace with three roles.** Theatre owners self-serve (BookMyShow does this through contracts and box-office software; Frontrow does it in the product). New businesses are verified once by staff before going public.
4. **Shared film catalogue.** Staff create every film once; theatre owners pick films and add shows; owners request missing films. One page per film lists every cinema showing it.
5. **Customer flow = BookMyShow's**, with three changes: an email code instead of a phone OTP, no city step, and no add-ons (no food, donation, offers or coupons).
6. **Sign-in by email code only** for all roles — no passwords, no Google. Three doors: customers (`/sign-in`), businesses (`/business`), hidden staff (`/staff`, seeded accounts only). One email = one person; business access and the staff flag sit on top. Demo buttons for all three roles.
7. **Engine:** holds in Upstash Redis (one Lua script takes all seats or none, 10-minute TTL, version counter); sold seats in Postgres with `UNIQUE (show_id, seat_id)` as the final guard; v1 polls every 5 s, v2 pushes only on change.
8. **Payments:** Razorpay Checkout in test mode + webhook, deduplicated. Paid after the hold expired: seats still free → sell; sold to someone else → automatic refund.
9. **Counter sales:** theatre owners sell walk-in tickets (cash) on the same live map, so online and counter can never double-sell.
10. **Look:** direction B · Box office (Barlow Condensed / Barlow / JetBrains Mono, red actions, the cream stub that tears off on pay) on **paper pages with an oxblood header and a torn-stub edge** (chosen 2026-11-15).
11. **v4 = one Expo app for all three roles.** Customers get the whole flow plus an offline wallet and push; owners and staff get the jobs done on their feet (scanner, today board, counter; approvals, support).
12. **Free tiers only:** Vercel Hobby, Neon free, Upstash free; no pingers or frequent crons. No browser storage.
13. **Deploys run on GitHub Actions only** (2026-11-19): CI builds both apps on GitHub's runner and uploads the output to Vercel; Vercel's own Git deployments are disabled (`git.deploymentEnabled: false` in each `vercel.json`), so Vercel spends no build minutes.
14. **Door scanning with many scanners** (Viraj, 2026-11-19). v1 (B10): any number of ushers scan one show online; the server authorises every scan with one mark-used-once update, so a ticket admits exactly once. v4 (M5b): scanners download the show's signed ticket list before doors; offline, a matching scan is accepted **provisionally** and queued, and on reconnect the server reconciles — the first scan the **server commits** wins (`confirmed`), later ones are `duplicate_flagged`; device clocks (`scanned_at`) are audit-only. The counter shows confirmed and pending sync apart. **Honest limit:** two scanners that are both offline can each admit the same ticket — detected and flagged after sync, not prevented; a ticket refunded after a scanner downloaded its list stays valid on that scanner until it refreshes (flagged on sync).

## Versions
| Version | Ships | Proves | ~h |
|---|---|---|---|
| **v1 Box office** | Customer: home, search, movie page, language/format, showtimes, certificate notice, how many seats, seat map with holds, email code, summary, Razorpay, M-ticket + email, my tickets. Owner: register, cinemas, screens, pick films, bulk shows, bookings. Door scanning. Staff: film catalogue, film requests, approvals. New look; catalogue that never goes empty | A complete, working marketplace for all three roles | 26 left (+7 built) |
| **v2 Live hall** | Live seat updates, “Try it live” on the landing page, today board with live sales, blocked seats, counter sales, cancel a show; staff: cinema suspension, support, marketplace view | Realtime on serverless; a cinema runs its day on Frontrow | 13.75 |
| **v3 Full house** | Reviews after scan-in, waitlist for sold-out shows, sales reports, payouts, seat heatmap, review moderation | The money side and the features that need a full hall | 10 |
| **v4 In your pocket** | One Expo app: customer booking + offline wallet + push; owner scanner (multi-scanner door check-in (server-authorised online; provisional offline scans synced, duplicates flagged)), today board, counter; staff approvals + support | The API is a real product core; native where it matters; offline honesty at the door | 20.5 |

## The wow moment
Open two tabs on the same show. Pick a seat in one — it greys out in the other. Let the timer run out and it comes back in both. In v2 the landing page shows it side by side.

## Out of scope
Concerts and events · city selection · add-ons (food, donation, offers, coupons) · customer cancellations · Google or phone sign-in · cinema pages and favourites · reminder emails · coming soon + notify me · pick for me · view from your seat · ticket transfer · dynamic pricing · per-door ticket partitioning for scanners (v4 flags offline duplicates, doesn't prevent them) · real money · store listings.

## Success criteria
- Two concurrent requests for the same seat never both succeed — a test in CI.
- A confirmed booking always maps to exactly one ticket row per seat (unique constraint, tested).
- A stranger books a film on a phone and is scanned in at the door in under two minutes using the demo.
- A new theatre owner goes from registration to a bookable show (after approval) in under three minutes.
- v2: a hold or release is visible in every open seat map within ~1 s.
- v4: the same ticket scanned offline on two scanners, then synced (either order), yields exactly one `confirmed` and one `duplicate_flagged` and is counted once — a test.
