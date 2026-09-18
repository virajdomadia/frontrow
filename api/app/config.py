"""Settings: every api/ env var from docs/04-technical-design.md §13.

Secrets are `SecretStr | None` so the app imports and serves `/health` with no environment at all
(CI has no secrets) and never reprs a secret. Keys arrive just-in-time per plan row: Neon in S2,
Upstash in F2, Razorpay in F5, Resend + Blob in L5.
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

    # --- Holds (Upstash Redis, TCP URL) — F2 ---
    redis_url: SecretStr | None = None

    # --- Payments (Razorpay test mode) — F5 ---
    razorpay_key_id: str | None = None
    razorpay_key_secret: SecretStr | None = None
    razorpay_webhook_secret: SecretStr | None = None

    # --- Auth + tickets — F4 / F6 ---
    session_secret: SecretStr | None = None
    ticket_secret: SecretStr | None = None

    # --- Cross-service ---
    web_url: str = "http://localhost:3000"


@lru_cache
def get_settings() -> Settings:
    """FastAPI dependency; cached so the env file is read once per process."""
    return Settings()
