"""Transactional email over Gmail SMTP (04 §1, B2) — sign-in codes and ticket emails.

Ported from Tripsmith's sender: stdlib `smtplib` in a worker thread (STARTTLS on 587, a Google
app password), no new dependency. Which sender runs:

- `SMTP_HOST` + `SMTP_USER` + `SMTP_PASSWORD` set → `SmtpSender`.
- Not set, running locally → `LogSender`: the message (and so the code) goes to the api log, so
  the sign-in flow works on a laptop with no mailbox.
- Not set on a deployment (`VERCEL`) → `None`: sign-in by code answers 503 and the page points
  at the demo buttons. A deployment never pretends to have sent an email.

Tests put a recording sender on `app.state.mailer`.
"""

from __future__ import annotations

import asyncio
import logging
import os
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage as MimeMessage
from email.utils import formatdate, make_msgid
from html import escape
from typing import Protocol

from fastapi import FastAPI

from app.config import Settings

log = logging.getLogger(__name__)

SMTP_TIMEOUT_SECONDS = 15.0


@dataclass(frozen=True)
class Mail:
    to: str
    subject: str
    text: str
    html: str


class MailError(Exception):
    """A send that did not happen."""


class Mailer(Protocol):
    async def send(self, mail: Mail) -> None: ...


class LogSender:
    """Local development: log the message instead of sending it."""

    async def send(self, mail: Mail) -> None:
        log.warning(
            "email (not sent, no SMTP configured) to %s — %s\n%s", mail.to, mail.subject, mail.text
        )


class SmtpSender:
    def __init__(self, host: str, port: int, user: str, password: str, sender: str) -> None:
        self._host, self._port = host, port
        self._user, self._password = user, password
        self._from = sender

    def _mime(self, mail: Mail) -> MimeMessage:
        mime = MimeMessage()
        mime["From"] = self._from
        mime["To"] = mail.to
        mime["Subject"] = mail.subject
        mime["Date"] = formatdate(localtime=False)
        mime["Message-ID"] = make_msgid(domain=self._user.rsplit("@", 1)[-1])
        mime.set_content(mail.text)
        mime.add_alternative(mail.html, subtype="html")
        return mime

    def _send_blocking(self, mime: MimeMessage) -> None:
        with smtplib.SMTP(self._host, self._port, timeout=SMTP_TIMEOUT_SECONDS) as smtp:
            smtp.starttls()
            smtp.login(self._user, self._password)
            smtp.send_message(mime)

    async def send(self, mail: Mail) -> None:
        try:
            await asyncio.to_thread(self._send_blocking, self._mime(mail))
        except smtplib.SMTPException as exc:
            # Never the address: SMTPRecipientsRefused carries it, so no chained cause.
            raise MailError(f"SMTP refused: {type(exc).__name__}") from None
        except OSError as exc:  # DNS, connect, timeout
            raise MailError(f"SMTP unreachable: {type(exc).__name__}") from None


def mailer_for(app: FastAPI) -> Mailer | None:
    """The configured sender (cached on the app); None on a deployment with no SMTP."""
    if hasattr(app.state, "mailer"):
        return app.state.mailer
    settings: Settings = app.state.settings
    mailer: Mailer | None
    if settings.smtp_host and settings.smtp_user and settings.smtp_password:
        mailer = SmtpSender(
            settings.smtp_host,
            settings.smtp_port,
            settings.smtp_user,
            settings.smtp_password.get_secret_value(),
            settings.email_from,
        )
    elif os.environ.get("VERCEL"):
        log.error("SMTP_* is not set on this deployment: sign-in codes and ticket emails are off")
        mailer = None
    else:
        mailer = LogSender()
    app.state.mailer = mailer
    return mailer


def _page(heading: str, body_html: str) -> str:
    return (
        '<div style="font-family:Arial,sans-serif;background:#EFE7DA;padding:24px">'
        '<div style="max-width:480px;margin:auto;background:#FBF7F0;border-radius:10px;'
        'overflow:hidden;color:#2A0B1E">'
        '<div style="background:#7E1A22;color:#fff;padding:16px 20px;font-weight:700;'
        'letter-spacing:.06em;text-transform:uppercase">Frontrow</div>'
        f'<div style="padding:20px"><h1 style="font-size:20px;margin:0 0 12px">{heading}</h1>'
        f"{body_html}</div></div></div>"
    )


def code_mail(to: str, code: str, minutes: int) -> Mail:
    text = (
        f"Your Frontrow sign-in code is {code}.\n\n"
        f"It works for {minutes} minutes. If you didn't ask for it, ignore this email."
    )
    html = _page(
        "Your sign-in code",
        f'<p style="font-size:32px;font-weight:700;letter-spacing:.2em;margin:8px 0">{code}</p>'
        f"<p>It works for {minutes} minutes. If you didn't ask for it, ignore this email.</p>",
    )
    return Mail(to=to, subject=f"{code} is your Frontrow code", text=text, html=html)


def ticket_mail(to: str, *, title: str, when: str, cinema: str, seats: str, url: str) -> Mail:
    text = (
        f"You're booked: {title}\n{when} · {cinema}\nSeats: {seats}\n\n"
        f"Your M-ticket with the QR codes: {url}"
    )
    html = _page(
        f"You're booked: {escape(title)}",
        f"<p>{escape(when)} · {escape(cinema)}<br>Seats: <b>{escape(seats)}</b></p>"
        f'<p><a href="{escape(url)}" style="display:inline-block;background:#E63946;color:#fff;'
        'padding:10px 16px;border-radius:6px;text-decoration:none;font-weight:700">'
        "Open your M-ticket</a></p>",
    )
    return Mail(to=to, subject=f"Your tickets for {title}", text=text, html=html)
