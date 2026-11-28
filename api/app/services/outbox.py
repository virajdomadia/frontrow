"""The email outbox (L5): customer emails about money (a cancelled show, a refund, a resent
ticket) are recorded in the same transaction as the change they report, then sent after it
commits. A send that fails, or can't happen, never touches the money: it's a status on the row.

Statuses: `queued` (not tried yet) → `sent`, or `failed` (SMTP refused; the error is kept),
`not_sent` (no SMTP on this deployment), `logged` (local development: written to the log),
`skipped` (a demo account's address: demo users are never emailed). Staff read the outbox, so
a reviewer can see every email the system would have sent while SMTP is off.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from html import escape

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EmailOutbox
from app.services.auth import DEMO_DOMAIN
from app.services.mail import LogSender, Mail, Mailer, MailError, _page

SEND_AT_MOST = 25  # per request: a big show's emails go out over a few calls, not one long one


def queue(
    db: AsyncSession, *, to: str, subject: str, text: str, kind: str, order_id: uuid.UUID | None
) -> EmailOutbox:
    row = EmailOutbox(
        id=uuid.uuid4(), to_email=to, subject=subject, body=text, kind=kind, order_id=order_id
    )
    db.add(row)
    return row


def _mail(row: EmailOutbox) -> Mail:
    paragraphs = "".join(f"<p>{escape(p)}</p>" for p in row.body.split("\n\n"))
    return Mail(
        to=row.to_email, subject=row.subject, text=row.body, html=_page(row.subject, paragraphs)
    )


async def deliver(
    db: AsyncSession, mailer: Mailer | None, ids: list[uuid.UUID], *, now: datetime
) -> None:
    """Try the queued rows among `ids` (at most SEND_AT_MOST), one row per transaction so a slow
    SMTP server holds one row lock at a time, and two callers never send one email twice."""
    for _ in range(SEND_AT_MOST):
        row = await db.scalar(
            select(EmailOutbox)
            .where(EmailOutbox.id.in_(ids), EmailOutbox.status == "queued")
            .order_by(EmailOutbox.created_at)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        if row is None:
            break
        if row.to_email.rsplit("@", 1)[-1].endswith(DEMO_DOMAIN.lstrip("@")):
            # Demo accounts and the seeded bookers (@bookers.frontrow.demo) aren't real inboxes.
            row.status, row.error = "skipped", "demo account"
        elif mailer is None:
            row.status, row.error = "not_sent", "SMTP is not configured on this deployment"
        else:
            try:
                await mailer.send(_mail(row))
                row.status = "logged" if isinstance(mailer, LogSender) else "sent"
                row.sent_at = now
            except MailError as e:
                row.status, row.error = "failed", str(e)
        await db.commit()
