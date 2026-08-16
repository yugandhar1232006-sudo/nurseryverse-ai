"""Unit tests for app/core/config.py."""
from __future__ import annotations

import pytest

from app.core.config import Settings


@pytest.mark.unit
def test_default_settings_load_without_env():
    settings = Settings(_env_file=None)
    assert settings.APP_ENV == "development"
    assert settings.is_production is False


@pytest.mark.unit
def test_is_production_flag():
    settings = Settings(_env_file=None, APP_ENV="production")
    assert settings.is_production is True


@pytest.mark.unit
def test_async_and_sync_database_uris_differ_only_by_driver():
    settings = Settings(
        _env_file=None,
        POSTGRES_USER="u",
        POSTGRES_PASSWORD="p",
        POSTGRES_HOST="h",
        POSTGRES_PORT=5432,
        POSTGRES_DB="d",
    )
    assert settings.sqlalchemy_database_uri == "postgresql+psycopg://u:p@h:5432/d"
    assert settings.sqlalchemy_database_uri_async == "postgresql+asyncpg://u:p@h:5432/d"


@pytest.mark.unit
def test_cors_origins_has_a_sane_default():
    settings = Settings(_env_file=None)
    assert settings.CORS_ALLOWED_ORIGINS == ["http://localhost:3000"]
