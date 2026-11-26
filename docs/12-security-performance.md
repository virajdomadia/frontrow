# Frontrow — Security & performance checklist (v1)

**Lifecycle step:** 12 of 17 · **Walked:** 2026-11-26 against [05-architecture.md §7](05-architecture.md#7-security-notes-the-short-list) · one page, v1 only.

## Security (05 §7, walked item by item)
| Item | Status | Where |
|---|---|---|
| Session cookie HttpOnly + SameSite=Lax, Secure on https | ✅ | `api/app/services/auth.py` (`set_session_cookie`; Secure when `WEB_URL` is https) |
| Session ids stored as an HMAC of the token, never the token | ✅ | `token_id()`; keyed by `SESSION_SECRET` |
| argon2 passwords; unknown email costs the same as a wrong password | ✅ | `authenticate()` verifies against a dummy hash |
| Organiser routes check role **and** ownership; other organisers' ids are 404, not 403 | ✅ | `api/app/services/organiser.py` `own_*`; `tests/test_organiser.py` |
| Another customer's order / tickets → 404 | ✅ | `owned_order()`; `tests/test_orders.py::test_demo_pay_tickets_and_privacy` |
| Server-side totals only (tier prices + ₹30 fee); the client never sends a price | ✅ | `services/orders.create`; `test_order_total` |
| Razorpay Checkout signature verified (`order_id|payment_id`, key secret) | ✅ | `RazorpayGateway.signature_ok`; `test_verify_signature` |
| Webhook HMAC over the raw body + event-id dedupe in the same transaction as the confirm | ✅ | `routers/orders.razorpay_webhook`; `test_webhook_signature_and_replay` |
| Double-sell impossible even if Redis misbehaves (`UNIQUE (showtime_id, seat_id)`) | ✅ | `test_confirm_unique` |
| Ticket QR tokens HMAC-signed, expire 6 h after the show; `TICKET_SECRET` stays on the server | ✅ | `services/tickets.py` |
| Holds rate-limited per holder (30 / min) — a script can't grab a hall | ✅ | `holds.rate_limit`; `test_holds_rate_limited` |
| 10 seats per booking, enforced across tabs of one holder | ✅ | `test_hold_rules` |
| `?next=` after sign-in is same-site only (no open redirect) | ✅ | `web/src/lib/next-path.ts`; `web/tests/client.test.ts` |
| CSP: same-origin everything, plus only Razorpay's checkout/api origins; `frame-ancestors 'none'` | ✅ | `web/next.config.ts` |
| Bookings CSV is safe to open in a spreadsheet (formula injection) | ✅ | `organiser._csv_safe` |
| Poster / photo fields accept only paths into the bundled CC library (no arbitrary URLs) | ✅ | `schemas/organiser.ImagePath` |
| No PII in logs (no emails, tokens or payment ids logged except a refund failure's payment id) | ✅ | grep `log.` in `api/app` |
| CSRF: cookie auth + SameSite=Lax + JSON bodies (cross-site JSON needs a preflight the api never grants) | ✅ by design | no CORS middleware |
| Secrets missing in production fall back to dev keys with a warning | ⚠️ set `SESSION_SECRET` and `TICKET_SECRET` before deploy | `auth._secret`, `tickets._secret` |
| Forgot-password | ⏭ v2 (needs Resend) — the sign-in form says so | R7 |

## Performance
- Catalog pages stay ISR (60 s) — the header's account links read `/auth/me` in the browser so they don't make every page dynamic.
- Seat map: one poll every 5 s = 1 Postgres query + 1 Redis pipeline (`HGETALL` + `GET`); paused while the tab is hidden, immediate on return.
- A hold = 1 rate-limit pipeline + 1 Lua call + 2 small Postgres reads. Upstash budget per 04 §4 holds.
- QR codes are drawn on the server as inline SVG — no QR library in the client bundle.
- Route bundle sizes (`pnpm build`, 2026-11-26): `/book/[id]` 18.3 kB, `/checkout/[id]` 7.4 kB, `/tickets/[id]` 7.9 kB, shared 139 kB first load.

**Lighthouse:** the QA pass of 2026-11-19 measured landing / events / event page (PRD target ≥ 90 perf, 100 a11y, 100 SEO). Re-run on the production URL after this deploys; the new pages are dynamic and per-user, so landing / events / event page stay the scored set.
