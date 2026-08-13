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
from lpg.api.v1.routers import (
    admin,
    auth,
    customer,
    cylinder_ledger,
    dashboard,
    delivery,
    health,
    inventory,
    order,
    route,
)
from lpg.config.logging import configure_logging, get_logger
from lpg.config.settings import Settings, get_settings
from lpg.infrastructure.events.cylinder_ledger_handlers import (
    register_cylinder_ledger_handlers,
)
from lpg.infrastructure.events.dispatcher import DomainEventDispatcher
from lpg.infrastructure.health import (
    DatabaseHealthCheck,
    JobQueueHealthCheck,
    RedisHealthCheck,
    StorageHealthCheck,
)
from lpg.infrastructure.identity.jwt_signer import PyJwtSigner
from lpg.infrastructure.identity.password_hasher import Argon2PasswordHasher
from lpg.infrastructure.jobs.pool import JobQueue
from lpg.infrastructure.persistence.database import Database
from lpg.infrastructure.realtime.publisher import RedisRealtimePublisher
from lpg.infrastructure.redis.client import RedisClient
from lpg.infrastructure.storage.client import S3CompatibleFileStorage

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from lpg.application.common.ports import HealthCheck
    from lpg.application.identity.ports import JwtSigner, PasswordHasher

_logger = get_logger(__name__)


@dataclass
class AppState:
    """Process-wide resources owned by the application lifespan."""

    database: Database | None = None
    redis: RedisClient | None = None
    health_checks: list[HealthCheck] = field(default_factory=list)
    event_dispatcher: DomainEventDispatcher | None = None
    job_queue: JobQueue | None = None
    realtime_publisher: RedisRealtimePublisher | None = None
    storage: S3CompatibleFileStorage | None = None
    jwt_signer: JwtSigner | None = None
    password_hasher: PasswordHasher | None = None


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

    Database and Redis connections are created but not dialled here. If a
    dependency is briefly unavailable at boot the application still starts
    and reports itself *not ready* — which is correct. Refusing to start
    would mean an instance could never recover from a dependency that comes
    up a few seconds late.

    ``JobQueue`` is the one exception: ARQ's ``create_pool`` connects
    eagerly, with no lazy variant. A failure here is caught rather than
    left to propagate, so a Redis outage at boot degrades the queue to
    *not ready* — exactly like the other two — instead of preventing the
    application from starting at all.
    """
    settings = get_settings()

    database = Database(settings)
    database.connect()

    redis_client = RedisClient(settings)
    redis_client.connect()

    job_queue = JobQueue(settings)
    try:
        await job_queue.connect()
    except Exception as exc:  # noqa: BLE001 - degrade to not-ready, never crash startup
        _logger.warning("job_queue_connect_failed_at_startup", error=str(exc))

    # Same eager-connect exception as JobQueue: ensuring the bucket exists
    # (head_bucket/create_bucket) means storage.connect() makes a real network
    # call at boot. A failure degrades to not-ready rather than crashing startup.
    storage = S3CompatibleFileStorage(settings)
    try:
        await storage.connect()
    except Exception as exc:  # noqa: BLE001 - degrade to not-ready, never crash startup
        _logger.warning("storage_connect_failed_at_startup", error=str(exc))

    # Unlike Database/Redis/JobQueue/Storage above, a JWT signer with no
    # configured key is not a transient dependency outage to degrade past —
    # it is a configuration error that would affect every request for as
    # long as the process runs. `PyJwtSigner.__init__` raises `RuntimeError`
    # in that case (deliberately uncaught here), matching the same
    # fail-loud-at-startup philosophy `Settings.model_post_init` already
    # applies to a wildcard CORS origin or `debug=True` outside local dev.
    jwt_signer = PyJwtSigner(settings)
    password_hasher = Argon2PasswordHasher(settings)

    _state.database = database
    _state.redis = redis_client
    _state.event_dispatcher = DomainEventDispatcher()
    register_cylinder_ledger_handlers(_state.event_dispatcher, database)
    _state.job_queue = job_queue
    _state.realtime_publisher = RedisRealtimePublisher(redis_client)
    _state.storage = storage
    _state.jwt_signer = jwt_signer
    _state.password_hasher = password_hasher
    _state.health_checks = [
        DatabaseHealthCheck(database),
        RedisHealthCheck(redis_client),
        JobQueueHealthCheck(job_queue),
        StorageHealthCheck(storage),
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
        await job_queue.disconnect()
        await storage.disconnect()
        _state.database = None
        _state.redis = None
        _state.event_dispatcher = None
        _state.job_queue = None
        _state.storage = None
        _state.realtime_publisher = None
        _state.jwt_signer = None
        _state.password_hasher = None
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
            {
                "name": "Authentication",
                "description": "Login, OTP, refresh, logout, password reset (Phase 6).",
            },
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

    # API v1
    app.include_router(auth.router, prefix=settings.api_v1_prefix)
    app.include_router(admin.router, prefix=settings.api_v1_prefix)
    app.include_router(customer.router, prefix=settings.api_v1_prefix)
    app.include_router(cylinder_ledger.router, prefix=settings.api_v1_prefix)
    app.include_router(delivery.router, prefix=settings.api_v1_prefix)
    app.include_router(inventory.router, prefix=settings.api_v1_prefix)
    app.include_router(order.router, prefix=settings.api_v1_prefix)
    app.include_router(route.router, prefix=settings.api_v1_prefix)
    app.include_router(dashboard.router, prefix=settings.api_v1_prefix)

    return app


app = create_app()
