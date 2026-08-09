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


class TestDiscreteConnectionParts:
    """LPG_DB_* parts, composed into a DSN.

    This is the shape a hosting provider hands you, and it means rotating a
    password touches one variable rather than requiring a whole DSN rewrite.
    """

    def test_composes_a_dsn_from_parts(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("LPG_DATABASE_URL", raising=False)
        monkeypatch.setenv("LPG_DB_HOST", "db.example.supabase.co")
        monkeypatch.setenv("LPG_DB_PORT", "5432")
        monkeypatch.setenv("LPG_DB_NAME", "postgres")
        monkeypatch.setenv("LPG_DB_USER", "postgres")
        monkeypatch.setenv("LPG_DB_PASSWORD", "simplepass")

        url = Settings().effective_database_url

        assert url == (
            "postgresql+asyncpg://postgres:simplepass@db.example.supabase.co:5432/postgres"
        )

    def test_url_encodes_special_characters_in_the_password(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The footgun this exists to remove.

        An unencoded "@" is read as the host separator, so the driver reports
        "could not translate host name" rather than an authentication failure —
        sending you to debug DNS instead of the password.
        """
        monkeypatch.delenv("LPG_DATABASE_URL", raising=False)
        monkeypatch.setenv("LPG_DB_HOST", "db.example.supabase.co")
        monkeypatch.setenv("LPG_DB_USER", "postgres")
        monkeypatch.setenv("LPG_DB_PASSWORD", "p@ss:w/rd?#1")

        url = Settings().effective_database_url

        assert "p%40ss%3Aw%2Frd%3F%231" in url
        assert "@db.example.supabase.co" in url
        # Exactly one "@" — the credential separator.
        assert url.count("@") == 1

    def test_explicit_url_wins_over_discrete_parts(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(
            "LPG_DATABASE_URL", "postgresql+asyncpg://u:p@explicit-host:5432/explicit"
        )
        monkeypatch.setenv("LPG_DB_HOST", "discrete-host")
        monkeypatch.setenv("LPG_DB_USER", "discrete-user")

        assert "explicit-host" in Settings().effective_database_url

    def test_falls_back_to_the_local_default_when_nothing_is_set(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        for var in ("LPG_DATABASE_URL", "LPG_DB_HOST", "LPG_DB_USER"):
            monkeypatch.delenv(var, raising=False)

        assert "localhost" in Settings().effective_database_url

    def test_password_is_not_exposed_in_repr(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """SecretStr keeps the value out of logs, tracebacks and error messages."""
        monkeypatch.setenv("LPG_DB_PASSWORD", "super-secret-value")

        settings = Settings()

        assert "super-secret-value" not in repr(settings)
        assert "super-secret-value" not in str(settings)
        assert settings.db_password is not None
        assert settings.db_password.get_secret_value() == "super-secret-value"

    def test_uat_is_a_valid_environment(self) -> None:
        assert Settings(environment="uat").environment == "uat"

    def test_uat_is_held_to_non_local_guard_rails(self) -> None:
        with pytest.raises(ValueError, match="Wildcard CORS origin"):
            Settings(environment="uat", cors_origins=["*"])
