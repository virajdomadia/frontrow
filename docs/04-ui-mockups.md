# Frontrow — UI Mockups

**Lifecycle step:** 4 of 17 (UX companion to the technical design) · **Brief locked:** 2026-09-15 · **Variants:** built 2026-09-15 — `mockups/direction-variants.html`, published at https://claude.ai/artifact/LFJw5Zg1LEvvYjqdhot2Dr · **awaiting Viraj's pick.**
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

Recommendation: **A + B** as the signature pair (load moment + the hold moment), **D** as a small v2 touch. Viraj picks on the variant page; the winner is written here with tokens.

## Variant page (`mockups/direction-variants.html`) — round 1, built
Four full-size directions of S4 (cinema grid, 14 rows / 234 seats, seeded sold + 6 held by others + G9/G10 mine, shared 10-minute countdown, "someone else" takes or releases a seat every ~7 s) and S3 on a 390 px phone, behind an A/B/C/D tab strip. Each demonstrates its motion candidate live: **A House lights** (sweep + burning ring), **B Box office** (cream stub, press Pay to tear it off), **C Blueprint** (rows plot in, fuse countdown), **D Stage view** (perspective map, ripple on others' holds). Real CC photos in `mockups/img/` (credits in `mockups/img/CREDITS.md`); Google Fonts only; `prefers-reduced-motion` respected.

## After the pick
- Record: chosen direction, tokens (colours, radii, seat sizes, motion durations/easings), font loading plan → this file.
- `mockups/screens.html`: S1 (update), S2, S3, S4 ×3 templates, S5, S6, S7, S8, S9, S10–S13 organiser. Organiser screens may be plainer but same tokens.
- Themed browser surfaces: `::selection` amber on plum, scrollbar plum-2 track / muted thumb, focus ring amber 3 px, `caret-color` red, `theme-color` plum.
