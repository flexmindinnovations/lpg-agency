"""Application configuration.

Settings are loaded from environment variables through Pydantic v2's
``BaseSettings``. This is the single place the application reads configuration:
``os.environ`` is never consulted elsewhere, so every knob is discoverable,
typed, and validated at startup rather than at first use.

Failing loudly at startup on missing or malformed configuration is deliberate.
A service that boots with a silently-defaulted database URL and only fails on
the first request is far harder to diagnose than one that refuses to start.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, PostgresDsn, RedisDsn, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

Environment = Literal["local", "dev", "qa", "staging", "production"]


class Settings(BaseSettings):
    """Runtime configuration, sourced from the environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="LPG_",
        extra="ignore",
        case_sensitive=False,
    )

    # -- Application ------------------------------------------------------
    app_name: str = "LPG Agency Management Platform"
    app_version: str = "0.1.0"
    environment: Environment = "local"
    debug: bool = False

    # -- API --------------------------------------------------------------
    api_v1_prefix: str = "/api/v1"
    docs_enabled: bool = True

    # -- CORS -------------------------------------------------------------
    # Defaults cover the Nx dev server only. Production origins are supplied
    # by environment; a wildcard is rejected outright in non-local
    # environments (see model_post_init below).
    #
    # NoDecode is required: without it pydantic-settings tries to JSON-decode
    # any complex-typed field before validators run, so the natural
    # comma-separated form ("a,b") raises a parse error rather than reaching
    # the validator below.
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:4200"]
    )
    cors_allow_credentials: bool = True

    # -- Database ---------------------------------------------------------
    # The application connects as a non-superuser role without BYPASSRLS, so
    # PostgreSQL Row-Level Security remains an effective tenant-isolation
    # backstop (ADR-017). Hosted on Supabase (ADR-027); local development uses
    # the docker compose PostgreSQL.
    #
    # No credential is ever hardcoded. The default below points at the local
    # docker compose stack whose password is worthless outside the container.
    database_url: PostgresDsn = Field(
        default=PostgresDsn(
            "postgresql+asyncpg://lpg_app:dev_only_not_a_real_secret@localhost:55432/lpg_dev"
        )
    )

    # Alembic connects separately, for two reasons: migrations run as the
    # elevated role rather than the application role
    # (`06-database-architecture.md` §10), and they need a *direct* connection
    # rather than a transaction-mode pooler, which cannot support the
    # session-level state some DDL requires.
    #
    # Falls back to `database_url` when unset, which is correct for local
    # development where both are the same host.
    migration_database_url: PostgresDsn | None = None

    database_echo: bool = False
    database_pool_size: int = Field(default=10, ge=1, le=100)
    database_max_overflow: int = Field(default=5, ge=0, le=100)
    database_pool_timeout_seconds: int = Field(default=30, ge=1)

    # asyncpg caches prepared statements per connection. Behind a
    # transaction-mode pooler (Supabase's Supavisor, or PgBouncer) a connection
    # is handed to a different client between statements, so a cached prepared
    # statement is looked up on a backend that never prepared it — surfacing as
    # intermittent "prepared statement does not exist" errors under load, which
    # are miserable to diagnose because they do not reproduce at low traffic.
    #
    # Set to 0 when connecting through a transaction pooler. Left at the
    # default for direct connections, where caching is a genuine win.
    database_statement_cache_size: int = Field(default=100, ge=0)

    # -- Redis ------------------------------------------------------------
    # Serves cache, sessions, rate limiting, the job queue, and the real-time
    # Pub/Sub backplane (ADR-015). A critical dependency, monitored as one.
    redis_url: RedisDsn = Field(default=RedisDsn("redis://localhost:56379/0"))

    # -- Observability ----------------------------------------------------
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    log_json: bool = True
    correlation_id_header: str = "X-Correlation-ID"

    # -- Health -----------------------------------------------------------
    health_check_timeout_seconds: float = Field(default=3.0, gt=0)

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_cors_origins(cls, value: object) -> object:
        """Accept a comma-separated string, since that is how env vars arrive.

        Also tolerates a JSON array, so both ``a,b`` and ``["a","b"]`` work —
        deployment tooling produces one or the other depending on the platform,
        and neither should be a configuration trap.
        """
        if isinstance(value, str):
            stripped = value.strip()
            if stripped.startswith("["):
                import json

                parsed = json.loads(stripped)
                return [str(origin).strip() for origin in parsed]
            return [origin.strip() for origin in stripped.split(",") if origin.strip()]
        return value

    @property
    def effective_migration_url(self) -> str:
        """Connection string Alembic should use.

        Falls back to the application URL when no separate migration URL is
        configured — correct locally, where both are the same host.
        """
        return str(self.migration_database_url or self.database_url)

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def is_local(self) -> bool:
        return self.environment == "local"

    def model_post_init(self, __context: object) -> None:
        """Reject configurations that are unsafe outside local development."""
        if not self.is_local:
            if "*" in self.cors_origins:
                msg = f"Wildcard CORS origin is not permitted in environment {self.environment!r}"
                raise ValueError(msg)
            if self.debug:
                msg = f"debug must be disabled in environment {self.environment!r}"
                raise ValueError(msg)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached settings instance.

    Cached because configuration is immutable for the process lifetime, and
    because re-reading and re-validating on every dependency resolution would
    be pure overhead. Tests clear the cache via ``get_settings.cache_clear()``.
    """
    return Settings()
