"""Database connection foundation.

Async SQLAlchemy 2.x engine and session factory, plus the tenant-context seam
that Row-Level Security depends on.

No ORM models are defined in Phase 1. The declarative base and the standard
column mixins live here so that when aggregates arrive they inherit the audit,
soft-delete and concurrency columns rather than each re-declaring them
(``docs/data/03-database-schema.md``).

**The tenant seam is the important part of this module.** Every request
transaction sets ``app.current_tenant_id`` before any query, because that is
what the RLS policies predicate on. It is set **transaction-scoped**, via
``set_config(..., is_local => true)``, so it cannot leak across pooled
connections — which also keeps this compatible with transaction-mode
server-side pooling, Supavisor on Supabase included
(``06-database-architecture.md`` §2, §14).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import MetaData, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from lpg.config.logging import get_logger

if TYPE_CHECKING:
    import uuid
    from collections.abc import AsyncIterator

    from lpg.config.settings import Settings

_logger = get_logger(__name__)

# Explicit constraint naming so Alembic autogenerate produces stable,
# predictable migration names instead of database-assigned ones. Matches the
# conventions in `06-database-architecture.md` §4.
NAMING_CONVENTION = {
    "ix": "idx_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Declarative base for all ORM models.

    Note this is the *persistence* model, deliberately distinct from the domain
    model. Repositories translate between the two. That mapping layer costs
    real effort and is accepted on purpose: it is what keeps the domain layer
    framework-free and unit-testable without a database.
    """

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class Database:
    """Owns the engine and session factory for the process lifetime."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._engine: AsyncEngine | None = None
        self._session_factory: async_sessionmaker[AsyncSession] | None = None

    @property
    def engine(self) -> AsyncEngine:
        if self._engine is None:
            msg = "Database.connect() has not been called"
            raise RuntimeError(msg)
        return self._engine

    def connect(self) -> None:
        """Create the engine and session factory. Does not open a connection.

        Engine creation is lazy about networking — the first real connection
        happens on first use, which keeps startup fast and lets the readiness
        endpoint be the thing that reports database availability.
        """
        # `statement_cache_size=0` disables asyncpg's prepared-statement cache,
        # which is required behind a transaction-mode pooler (Supavisor,
        # PgBouncer) and harmless-but-slower on a direct connection. Driven by
        # configuration rather than hardcoded, because which one applies
        # depends on the connection string, not the code.
        self._engine = create_async_engine(
            self._settings.effective_database_url,
            echo=self._settings.database_echo,
            pool_size=self._settings.database_pool_size,
            max_overflow=self._settings.database_max_overflow,
            pool_timeout=self._settings.database_pool_timeout_seconds,
            pool_pre_ping=True,
            connect_args={
                "statement_cache_size": self._settings.database_statement_cache_size,
            },
        )
        self._session_factory = async_sessionmaker(
            bind=self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
        _logger.info("database_engine_created")

    async def disconnect(self) -> None:
        if self._engine is not None:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None
            _logger.info("database_engine_disposed")

    @staticmethod
    async def _apply_tenant_context(session: AsyncSession, tenant_id: uuid.UUID | None) -> None:
        """Set ``app.current_tenant_id`` transaction-scoped, if given.

        `set_config(..., is_local => true)` rather than the literal `SET
        LOCAL` statement. Both are transaction-scoped and equivalent in
        effect, but PostgreSQL's `SET` command does **not** accept bind
        parameters — `SET LOCAL x = :tenant_id` is a syntax error at the
        placeholder. `set_config` is a normal function call, so the value
        binds properly and can never be string-interpolated into SQL.

        Transaction-scoped is the important part: the value must not survive
        on a pooled connection and be inherited by the next request, which
        would be a cross-tenant leak through the pool. It is also what keeps
        this compatible with transaction-mode server-side pooling (Supavisor
        on Supabase, PgBouncer).
        """
        if tenant_id is not None:
            await session.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
                {"tenant_id": str(tenant_id)},
            )

    async def session(self, *, tenant_id: uuid.UUID | None = None) -> AsyncIterator[AsyncSession]:
        """Yield a session bound to a transaction, optionally tenant-scoped.

        **Owns commit/rollback itself** — commits on clean exit, rolls back on
        exception. Correct for simple, self-contained database access with no
        separate transaction-boundary owner. **Not** what the Unit of Work
        dependency uses (``lpg.api.v1.dependencies.unit_of_work``): a
        ``UnitOfWork`` needs to control exactly when the transaction commits
        (a use case may call ``uow.commit()`` explicitly, mid-flow), which
        this method's automatic commit-on-exit would race against. That path
        uses ``open_session()`` instead.

        ``tenant_id`` is optional in Phase 1 only because authentication does
        not exist yet, so there is no JWT to resolve a tenant from. From Phase 6
        onward the API dependency that produces sessions will require a
        resolved tenant context, making an unscoped session impossible to
        obtain through the normal request path (``03-backend-architecture.md``
        §3.1). Recorded as DW-12.
        """
        if self._session_factory is None:
            msg = "Database.connect() has not been called"
            raise RuntimeError(msg)

        async with self._session_factory() as session:
            await self._apply_tenant_context(session, tenant_id)
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def open_session(
        self, *, tenant_id: uuid.UUID | None = None
    ) -> AsyncIterator[AsyncSession]:
        """Yield a tenant-scoped session with **no automatic commit/rollback**.

        The caller owns the transaction boundary entirely — this is what
        ``SqlAlchemyUnitOfWork`` wraps. If the caller never commits or rolls
        back explicitly, closing the session at the end of this generator
        implicitly discards any pending transaction (SQLAlchemy's normal
        behaviour for a session closed with open work) — the fail-safe
        default is "nothing is persisted", never "silently committed".
        """
        if self._session_factory is None:
            msg = "Database.connect() has not been called"
            raise RuntimeError(msg)

        async with self._session_factory() as session:
            await self._apply_tenant_context(session, tenant_id)
            yield session

    async def ping(self) -> bool:
        """Return whether the database is reachable. Used by readiness."""
        try:
            async with self.engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
        except Exception as exc:  # noqa: BLE001 - readiness reports, never raises
            _logger.warning("database_ping_failed", error=str(exc))
            return False
        return True


class AuditColumnsMixin:
    """Standard audit columns required on every business table.

    Declared here rather than per-model so a future aggregate cannot
    accidentally ship without them. See ``docs/data/03-database-schema.md``
    §Standard Fields.

    Not applied to anything in Phase 1 — no tables exist yet.
    """

    __abstract__ = True

    # Concrete column definitions arrive with the first migration in Phase 2,
    # where they can be validated against a real schema rather than asserted
    # against nothing.
    _standard_columns: tuple[str, ...] = (
        "id",
        "tenant_id",
        "created_at",
        "created_by",
        "updated_at",
        "updated_by",
        "is_deleted",
        "deleted_at",
        "deleted_by",
        "version",
    )


def build_database(settings: Settings | None = None, **_: Any) -> Database:
    """Construct a Database from settings."""
    from lpg.config.settings import get_settings

    return Database(settings or get_settings())
