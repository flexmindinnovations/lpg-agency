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
