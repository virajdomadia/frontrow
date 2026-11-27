"""Settings: every api/ env var from docs/04-technical-design.md §13.

Secrets are `SecretStr | None` so the app imports and serves `/health` with no environment at all
(CI has no secrets) and never reprs a secret. Keys arrive just-in-time per plan row: Neon in S2,
Upstash + Gmail in B2, Razorpay in B6.
"""

from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env.local", env_file_encoding="utf-8", extra="ignore"
    )

    # --- Database (Neon; asyncpg URL). TEST_DATABASE_URL is dev/CI only. ---
    database_url: SecretStr | None = None
    test_database_url: SecretStr | None = None

    # --- Holds (Upstash Redis, TCP URL) — F2. TEST_REDIS_URL is dev/CI only. ---
    redis_url: SecretStr | None = None
    test_redis_url: SecretStr | None = None
    hold_ttl_seconds: int = 600  # 10 minutes (R4); tests shorten it
    holds_per_minute: int = 30  # rate limit per holder (06 §B)

    # --- Payments (Razorpay test mode) — F5 ---
    razorpay_key_id: str | None = None
    razorpay_key_secret: SecretStr | None = None
    razorpay_webhook_secret: SecretStr | None = None

    # --- Auth + tickets — B2 / B7 ---
    session_secret: SecretStr | None = None
    ticket_secret: SecretStr | None = None
    code_ttl_seconds: int = 600  # sign-in code life (R1)
    # Shared with the web tier, which forwards the visitor's address with it (auth.client_ip).
    proxy_secret: SecretStr | None = None

    # --- Email: Gmail SMTP (B2). Unset → codes are logged locally, refused on a deployment ---
    smtp_host: str | None = None
    smtp_port: int = 587  # STARTTLS
    smtp_user: str | None = None
    smtp_password: SecretStr | None = None
    email_from: str = "Frontrow <no-reply@frontrow.local>"

    # --- Seed: real staff accounts (comma-separated emails) for the hidden /staff door ---
    staff_emails: str = ""

    # --- Cross-service ---
    web_url: str = "http://localhost:3000"

    @property
    def cookie_secure(self) -> bool:
        """Secure cookies whenever the site is served over https (production, previews)."""
        return self.web_url.startswith("https://")


@lru_cache
def get_settings() -> Settings:
    """FastAPI dependency; cached so the env file is read once per process."""
    return Settings()
