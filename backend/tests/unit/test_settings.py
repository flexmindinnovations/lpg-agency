"""Configuration loading and guard rails."""

from __future__ import annotations

import pytest
from pydantic import ValidationError as PydanticValidationError

from lpg.config.settings import Settings


class TestSettingsLoading:
    def test_loads_defaults_for_local(self) -> None:
        settings = Settings(environment="local")

        assert settings.environment == "local"
        assert settings.is_local
        assert not settings.is_production
        assert settings.api_v1_prefix == "/api/v1"

    def test_reads_from_environment_with_prefix(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LPG_LOG_LEVEL", "WARNING")
        monkeypatch.setenv("LPG_APP_VERSION", "9.9.9")

        settings = Settings()

        assert settings.log_level == "WARNING"
        assert settings.app_version == "9.9.9"

    def test_cors_origins_accept_comma_separated_string(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Environment variables are strings; a list has to be parsed from one."""
        monkeypatch.setenv("LPG_CORS_ORIGINS", "http://localhost:4200, https://app.example.com")

        settings = Settings()

        assert settings.cors_origins == [
            "http://localhost:4200",
            "https://app.example.com",
        ]

    def test_rejects_invalid_log_level(self) -> None:
        with pytest.raises(PydanticValidationError):
            Settings(log_level="CHATTY")

    def test_rejects_invalid_pool_size(self) -> None:
        with pytest.raises(PydanticValidationError):
            Settings(database_pool_size=0)


class TestProductionGuardRails:
    """Configuration that is fine locally and dangerous in production.

    These fail at startup rather than at first request. A service that boots
    with a wildcard CORS origin and only reveals it under attack is far worse
    than one that refuses to start.
    """

    def test_wildcard_cors_rejected_outside_local(self) -> None:
        with pytest.raises(ValueError, match="Wildcard CORS origin"):
            Settings(environment="production", cors_origins=["*"], debug=False)

    def test_debug_rejected_outside_local(self) -> None:
        with pytest.raises(ValueError, match="debug must be disabled"):
            Settings(environment="production", debug=True)

    def test_wildcard_permitted_locally(self) -> None:
        settings = Settings(environment="local", cors_origins=["*"], debug=True)

        assert settings.cors_origins == ["*"]


class TestDatabaseConnectionSettings:
    """Configuration for the Supabase-hosted database (ADR-027).

    Nothing here hardcodes a credential. The local defaults point at the docker
    compose stack, whose password is worthless outside the container.
    """

    def test_migration_url_falls_back_to_the_application_url(self) -> None:
        """Correct locally, where both are the same host."""
        settings = Settings(environment="local")

        assert settings.migration_database_url is None
        assert settings.effective_migration_url == str(settings.database_url)

    def test_migration_url_overrides_when_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Migrations run as the elevated role over a direct connection, not as
        the application role through a transaction pooler."""
        monkeypatch.setenv(
            "LPG_MIGRATION_DATABASE_URL",
            "postgresql+asyncpg://admin:pw@db.example.supabase.co:5432/postgres",
        )

        settings = Settings()

        assert "admin" in settings.effective_migration_url
        assert settings.effective_migration_url != str(settings.database_url)

    def test_statement_cache_can_be_disabled_for_transaction_pooling(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Required behind Supavisor or PgBouncer in transaction mode.

        asyncpg caches prepared statements per connection; a transaction pooler
        hands that connection to a different client between statements, so the
        cached statement is looked up on a backend that never prepared it.
        """
        monkeypatch.setenv("LPG_DATABASE_STATEMENT_CACHE_SIZE", "0")

        assert Settings().database_statement_cache_size == 0

    def test_statement_cache_rejects_negative_values(self) -> None:
        with pytest.raises(PydanticValidationError):
            Settings(database_statement_cache_size=-1)

    def test_accepts_a_supabase_pooler_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(
            "LPG_DATABASE_URL",
            "postgresql+asyncpg://app_user:pw@aws-0-eu-west-2.pooler.supabase.com:6543/postgres",
        )

        settings = Settings()

        # PostgresDsn is a multi-host URL type, so assert on the rendered
        # string rather than a `.port` attribute it does not expose.
        rendered = str(settings.database_url)
        assert "pooler.supabase.com" in rendered
        assert ":6543" in rendered
        assert rendered.startswith("postgresql+asyncpg://")


class TestNoHardcodedCredentials:
    def test_defaults_reference_only_the_local_container(self) -> None:
        """A default that reached a real host would be a live-credential leak
        the moment someone ran the app without an .env."""
        settings = Settings(environment="local")

        for url in (str(settings.database_url), str(settings.redis_url)):
            assert "localhost" in url or "127.0.0.1" in url
            assert "supabase" not in url
