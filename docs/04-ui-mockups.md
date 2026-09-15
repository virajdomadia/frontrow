# Frontrow — UI Mockups

**Lifecycle step:** 4 of 17 (UX companion to the technical design) · **Brief locked:** 2026-09-15 · **Variants:** built 2026-09-15 — `mockups/direction-variants.html`, published at https://claude.ai/artifact/LFJw5Zg1LEvvYjqdhot2Dr · **Chosen: B · Box office** (Viraj, 2026-09-15).
**Pairs with:** [03-user-flows.md](03-user-flows.md) — one mockup per v1 screen (S1–S13) after the direction is chosen.
**Files:** `mockups/landing.html` (exists, already ported to `web/`) → `mockups/direction-variants.html` (S4 seat map + S3 event page, desktop and 390 px) → `mockups/screens.html` (every v1 screen in the chosen direction).

## Brief
**Style:** a night at the movies — dark house, lit screen. The existing landing sets it: plum `#2A0B1E` ground, warm off-white "screen" `#F5EFE6`, red `#E63946` for the action, amber `#F4A261` for focus and warnings, Barlow Condensed uppercase headlines with Barlow for UI. Keep it; the variants explore how the **seat map** lives in it, not a new palette.

**The seat map is the product.** It must read instantly on a phone: tier colours, grey = someone else's, dark = sold, red = mine with a visible countdown. The arena needs a section overview → zoom. Dense grids must stay tappable (≥ 24 px seats at 390 px, or zoom).

## Motion signature — pick one in the variant page
| Candidate | What happens | Reduced-motion fallback |
|---|---|---|
| **A · House lights** | On load the hall is dim; a light sweeps from the screen to the back, revealing rows as it passes (staggered opacity by row). Taking a seat "lights" it. | Rows fade in together, 200 ms |
| **B · Burning fuse** | Each held seat gets a ring that burns down over 10 min (conic gradient driven by one rAF clock); the footer timer is the same ring, larger. Expiry: the ring snaps and the seat dims. | Static ring with numeric mm:ss |
| **C · Tear-off ticket** | On payment success the checkout card tears along a perforation (clip-path + slight rotation) and the ticket slides up with the QR drawing itself. | Cross-fade to the ticket |
| **D · Ripple take** | When *someone else* takes a seat, a single ripple emanates from it as it greys — the two-tab moment made visible. | Instant grey |

Recommendation was A + B; **Viraj chose B (2026-09-15)**. Signature = the ticket stub that fills as you pick and **tears off on pay**; seats pop in row by row on load. D's ripple stays on the table as a small v2 touch when the live map lands.

## Variant page (`mockups/direction-variants.html`) — round 1, built
Four full-size directions of S4 (cinema grid, 14 rows / 234 seats, seeded sold + 6 held by others + G9/G10 mine, shared 10-minute countdown, "someone else" takes or releases a seat every ~7 s) and S3 on a 390 px phone, behind an A/B/C/D tab strip. Each demonstrates its motion candidate live: **A House lights** (sweep + burning ring), **B Box office** (cream stub, press Pay to tear it off), **C Blueprint** (rows plot in, fuse countdown), **D Stage view** (perspective map, ripple on others' holds). Real CC photos in `mockups/img/` (credits in `mockups/img/CREDITS.md`); Google Fonts only; `prefers-reduced-motion` respected.

## Chosen direction — B · Box office (locked 2026-09-15)
**Idea:** the plum hall is the stage, the cream **ticket stub** is the object you build. Customer surfaces are plum; the stub, checkout and tickets are paper. Organiser console is plum with paper cards. Reads as ticketing at a glance (the pattern people trust) and the signature moment — the stub tearing along its perforation into a QR ticket — sits at the emotional peak, payment.

### Tokens (→ `web/src/app/globals.css`)
| Token | Value | Use |
|---|---|---|
| `--plum` / `--plum-2` / `--plum-3` | `#2A0B1E` / `#3A1230` / `#4A1A3E` | page ground / cards on plum / hover |
| `--screen` | `#F5EFE6` | text on plum, the "screen" |
| `--paper` / `--paper-2` | `#F5EFE6` / `#EADFD0` | stub, checkout, ticket / inset panels |
| `--ink` / `--ink-2` | `#2A0B1E` / `#5A3A50` | text on paper / secondary on paper |
| `--red` / `--red-dark` | `#E63946` / `#B8232F` | primary action, "mine" seats / red text on paper (contrast) |
| `--amber` | `#F4A261` | focus ring, warnings, "filling fast" |
| `--muted` / `--muted-2` | `#C9B3C1` / `#AE96A6` | secondary / tertiary text on plum (≥ 4.5:1) |
| `--held` / `--sold` | `#6B5566` / `#3A1230` (+ 1px `rgba(245,239,230,.14)` stroke) | someone else's / sold seats |
| `--classic` / `--prime` / `--recliner` | `#8FB8DE` / `#E9C46A` / `#C77DFF` | tiers |
| radii | seats 3 px · chips 5 px · buttons 6 px · stub/cards 10 px · phone 38 px | |
| seat | 26 px (recliner 36) · gap 8 · aisle 44 · centre aisle only | ≥ 24 px tap at 390 px via horizontal scroll/zoom |
| type | **Barlow Condensed** 700/800 uppercase for headings, prices, chips · **Barlow** 400/500/600 for UI · **JetBrains Mono** 500 for the countdown only | `next/font/google`, `display: swap` |

### Motion (all with `prefers-reduced-motion` fallbacks = instant)
| Moment | Spec |
|---|---|
| Map load | rows `popIn` 400 ms ease-out, stagger 40 ms/row (scale .7 → 1, opacity 0 → 1) |
| Stub enters | `slideIn` 600 ms cubic-bezier(.2,.8,.2,1), 200 ms delay (x 40 px → 0) |
| Seat toggle | fill 180 ms; hover scale 1.14 |
| Countdown | mono `mm:ss`, red on `--paper-2`; tab title mirrors it |
| **Pay → ticket (signature)** | stub `tear` 1.1 s cubic-bezier(.5,0,.8,.4): tilt −1.5° then rotate −8° and fall 120 % · ticket `riseIn` 700 ms after 600 ms · QR draws in |
| Someone else takes a seat | fill → `--held` 180 ms (v2 adds D's amber ripple) |

### Browser surfaces
`::selection` amber on plum · scrollbar: plum-2 track, muted thumb · focus ring amber 3 px offset 3 px · `caret-color` red · `theme-color` plum · favicon = brand mark.

## Screens (`mockups/screens.html`) — built 2026-09-15
Published at https://claude.ai/artifact/MCedtstCq6C2o7d9vJacPp. Every v1 screen from the screen index in direction B: S1 landing (now-showing strip + demo logins), S2 events list, S3 event page, S4 seat map (desktop + phone with bottom-sheet stub), S5 checkout (incl. the confirming state), S6 ticket, S7 my tickets, S8 refunded, S9 sign-up, S10 venues with live template preview, S11 events, S12 showtimes with the cancel guard, S13 bookings. Organiser screens use the same tokens with plainer motion. **Step 4 complete.**
