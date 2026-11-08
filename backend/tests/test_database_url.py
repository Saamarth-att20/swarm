"""Hosted Postgres addresses are rewritten so the async driver accepts them. Author: Saamarth Attray"""
from app.db import normalize_database_url


def test_plain_postgres_address_uses_the_async_driver():
    assert normalize_database_url("postgres://u:p@host/db") == "postgresql+asyncpg://u:p@host/db"
    assert normalize_database_url("postgresql://u:p@host/db") == "postgresql+asyncpg://u:p@host/db"


def test_neon_style_ssl_options_are_translated():
    url = "postgresql://u:p@ep-x.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
    assert normalize_database_url(url) == "postgresql+asyncpg://u:p@ep-x.us-east-2.aws.neon.tech/neondb?ssl=require"


def test_other_query_options_are_kept():
    assert normalize_database_url("postgresql://u:p@h/db?sslmode=require&application_name=swarm") == (
        "postgresql+asyncpg://u:p@h/db?ssl=require&application_name=swarm"
    )


def test_sqlite_and_already_normalised_urls_are_untouched():
    assert normalize_database_url("sqlite:///./x.db") == "sqlite+aiosqlite:///./x.db"
    assert normalize_database_url("sqlite+aiosqlite:///./x.db") == "sqlite+aiosqlite:///./x.db"
    assert normalize_database_url("postgresql+asyncpg://u:p@h/db?ssl=require") == "postgresql+asyncpg://u:p@h/db?ssl=require"