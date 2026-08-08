"""Application factory and composition root.

This is the one module permitted to import from every layer. A composition root
is by definition the place that knows how the pieces fit together — every other
module depends only on the layer beneath it. The ``import-linter`` contracts
carry a documented exception for this file, and only this file.

Phase 1 wires foundation concerns only: settings, logging, correlation IDs,
RFC 7807 error handling, CORS, OpenAPI, and the database and Redis connections.
No authentication, no business routers.
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from lpg.api.middleware.correlation import CorrelationIdMiddleware
from lpg.api.middleware.problem_details import register_exception_handlers
from lpg.api.v1.routers import health
from lpg.config.logging import configure_logging, get_logger
from lpg.config.settings import Settings, get_settings
from lpg.infrastructure.health import DatabaseHealthCheck, RedisHealthCheck
from lpg.infrastructure.persistence.database import Database
from lpg.infrastructure.redis.client import RedisClient

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from lpg.application.common.ports import HealthCheck

_logger = get_logger(__name__)


@dataclass
class AppState:
    """Process-wide resources owned by the application lifespan."""

    database: Database | None = None
    redis: RedisClient | None = None
    health_checks: list[HealthCheck] = field(default_factory=list)


_state = AppState()


def get_app_state() -> AppState:
    """Return the process-wide application state.

    A module-level singleton rather than a FastAPI dependency because the
    lifespan owns these resources and readiness needs them without a request
    scope.
    """
    return _state


def get_health_checks() -> list[HealthCheck]:
    """Return the registered dependency health checks."""
    return _state.health_checks


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:  # noqa: ARG001 - FastAPI signature
    """Open and close process-wide resources.

    Connections are created but not dialled here. If the database is briefly
    unavailable at boot the application still starts and reports itself
    *not ready* — which is correct. Refusing to start would mean an instance
    could never recover from a dependency that comes up a few seconds late.
    """
    settings = get_settings()

    database = Database(settings)
    database.connect()

    redis_client = RedisClient(settings)
    redis_client.connect()

    _state.database = database
    _state.redis = redis_client
    _state.health_checks = [
        DatabaseHealthCheck(database),
        RedisHealthCheck(redis_client),
    ]

    _logger.info(
        "application_started",
        app_name=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
    )

    try:
        yield
    finally:
        await database.disconnect()
        await redis_client.disconnect()
        _state.database = None
        _state.redis = None
        _state.health_checks = []
        _logger.info("application_stopped")


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the FastAPI application."""
    settings = settings or get_settings()

    configure_logging(level=settings.log_level, json_output=settings.log_json)

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "Multi-tenant SaaS platform for LPG distributors.\n\n"
            "All error responses follow RFC 7807 Problem Details, extended "
            "with a stable `error_code`. Success responses return the resource "
            "directly — there is no success envelope."
        ),
        lifespan=lifespan,
        # OpenAPI is served under the version prefix so the spec URL is
        # versioned alongside the API it describes (ADR-009).
        openapi_url=f"{settings.api_v1_prefix}/openapi.json" if settings.docs_enabled else None,
        docs_url=f"{settings.api_v1_prefix}/docs" if settings.docs_enabled else None,
        redoc_url=f"{settings.api_v1_prefix}/redoc" if settings.docs_enabled else None,
        # Route metadata *is* the contract — FastAPI generates the OpenAPI spec
        # from it, that spec is committed, and all three clients generate their
        # typed clients from the committed artifact (ADR-026).
        openapi_tags=[
            {"name": "Health", "description": "Liveness and readiness probes."},
        ],
    )

    # Middleware executes in reverse registration order, so CORS is registered
    # last to run first — a rejected pre-flight should not allocate a
    # correlation ID or touch the logging context.
    app.add_middleware(
        CorrelationIdMiddleware,
        header_name=settings.correlation_id_header,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=[settings.correlation_id_header],
    )

    register_exception_handlers(app)

    # Health endpoints sit outside the versioned prefix: they serve the
    # platform, not API clients, and their contract must not change when the
    # API version does.
    app.include_router(health.router)

    return app


app = create_app()
