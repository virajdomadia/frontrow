"""QR ticket tokens (04 §7).

    token = b64url("ticket_id:showtime_id:exp") + "." + b64url(hmac_sha256(secret, payload)[:16])

`exp` is the show's end + 6 h (unix seconds). The token is what the QR encodes; v2's check-in
verifies it and marks the ticket used once. `TICKET_SECRET` never leaves the server.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.config import Settings

log = logging.getLogger(__name__)

GRACE = timedelta(hours=6)
_DEV_SECRET = b"frontrow-dev-ticket-secret"
_warned = False


def _secret(settings: Settings) -> bytes:
    global _warned
    if settings.ticket_secret is not None:
        return settings.ticket_secret.get_secret_value().encode()
    if not _warned:
        log.warning("TICKET_SECRET is not set; using a development-only key")
        _warned = True
    return _DEV_SECRET


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def expiry_for(ends_at: datetime) -> datetime:
    return ends_at + GRACE


def sign(settings: Settings, ticket_id: uuid.UUID, showtime_id: uuid.UUID, exp: datetime) -> str:
    payload = f"{ticket_id}:{showtime_id}:{int(exp.timestamp())}".encode()
    mac = hmac.new(_secret(settings), payload, hashlib.sha256).digest()[:16]
    return f"{_b64(payload)}.{_b64(mac)}"


@dataclass(frozen=True)
class Verified:
    ticket_id: uuid.UUID
    showtime_id: uuid.UUID
    exp: int


def verify(settings: Settings, token: str, *, now: datetime) -> Verified | None:
    """The token's ids when the signature is good and it hasn't expired, else None."""
    try:
        body, mac = token.split(".", 1)
        payload = _unb64(body)
        expected = hmac.new(_secret(settings), payload, hashlib.sha256).digest()[:16]
        if not hmac.compare_digest(expected, _unb64(mac)):
            return None
        ticket, showtime, exp = payload.decode().split(":")
        verified = Verified(uuid.UUID(ticket), uuid.UUID(showtime), int(exp))
    except (ValueError, UnicodeDecodeError):
        return None
    if verified.exp < now.timestamp():
        return None
    return verified
