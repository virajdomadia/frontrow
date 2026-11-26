from app.db import asyncpg_url


def test_neon_dashboard_url_becomes_an_asyncpg_url() -> None:
    neon = (
        "postgresql://neondb_owner:pw@ep-x-pooler.ap-southeast-1.aws.neon.tech/neondb"
        "?sslmode=require&channel_binding=require"
    )
    assert asyncpg_url(neon) == (
        "postgresql+asyncpg://neondb_owner:pw@ep-x-pooler.ap-southeast-1.aws.neon.tech/neondb"
        "?ssl=require"
    )


def test_short_postgres_scheme_is_accepted() -> None:
    assert asyncpg_url("postgres://u:p@h/db") == "postgresql+asyncpg://u:p@h/db"


def test_a_ready_asyncpg_url_is_left_alone() -> None:
    url = "postgresql+asyncpg://frontrow@localhost:5498/frontrow_dev"
    assert asyncpg_url(url) == url
