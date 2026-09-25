"""Agency Provisioning (Phase 30): a Super Admin creating a new agency, through
the real use cases and repositories against real PostgreSQL.

Proves the parts unit tests cannot: that `tenant.tenant_provision()` really does
get a row past `tenant.tenant`'s RLS INSERT block, that the first admin ends up
with materialised permissions (a user without them logs in but gets 403 on
everything), that the audit row the repository writes by hand is accepted by the
`audit.audit_log` RLS policy, and that a failed invite really does close the
half-created tenant.
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from lpg.api.v1.dependencies.platform import PLATFORM_AUDIT_TENANT_ID
from lpg.application.common.errors import ConflictError
from lpg.application.common.tenant import RequestTenantContext
from lpg.application.identity.staff_user import InviteStaffUserUseCase
from lpg.application.tenant.manage_lifecycle import (
    CloseTenantCommand,
    CloseTenantUseCase,
    ListTenantsQuery,
    ListTenantsUseCase,
)
from lpg.application.tenant.provision_tenant import (
    ProvisionedTenant,
    ProvisionTenantCommand,
    ProvisionTenantUseCase,
)
from lpg.infrastructure.identity.token_hasher import Sha256TokenHasher
from lpg.infrastructure.persistence.database import Database
from lpg.infrastructure.persistence.repositories.identity import (
    SqlAlchemyIdentityUserRepository,
    SqlAlchemyPasswordResetTokenRepository,
    SqlAlchemyStaffUserRepository,
)
from lpg.infrastructure.persistence.repositories.tenant import SqlAlchemyTenantRepository
from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable, Callable

    from sqlalchemy.ext.asyncio import AsyncEngine

    from lpg.application.common.ports import UnitOfWork
    from lpg.config.settings import Settings

pytestmark = pytest.mark.integration

_ACTOR = uuid.uuid4()


class _RecordingEmailSender:
    def __init__(self) -> None:
        self.sent: list[str] = []

    async def send(self, to: str, subject: str, body: str) -> None:
        del subject, body
        self.sent.append(to)


class _FailingEmailSender:
    async def send(self, to: str, subject: str, body: str) -> None:
        del to, subject, body
        msg = "smtp exploded"
        raise RuntimeError(msg)


class _NoopStatusChecker:
    async def get_status(self, tenant_id: uuid.UUID) -> str:
        del tenant_id
        raise NotImplementedError

    async def invalidate(self, tenant_id: uuid.UUID) -> None:
        del tenant_id


@pytest.fixture
async def database(
    integration_settings: Settings, postgres_available: bool
) -> AsyncIterator[Database]:
    if not postgres_available:
        pytest.skip("PostgreSQL is not reachable — start it with ./scripts/dev-up.sh")
    db = Database(integration_settings)
    db.connect()
    try:
        yield db
    finally:
        await db.disconnect()


@pytest.fixture
async def admin_engine(postgres_available: bool) -> AsyncIterator[AsyncEngine]:
    if not postgres_available:
        pytest.skip("PostgreSQL is not reachable — start it with ./scripts/dev-up.sh")
    engine = create_async_engine(
        "postgresql+asyncpg://lpg_admin:dev_only_not_a_real_secret@localhost:5433/lpg_test"
    )
    try:
        yield engine
    finally:
        await engine.dispose()


@asynccontextmanager
async def _platform_uow(
    database: Database, tenant_id: uuid.UUID | None = None
) -> AsyncIterator[UnitOfWork]:
    """Mirrors `get_platform_unit_of_work_factory`'s `_open` exactly."""
    context = RequestTenantContext(tenant_id=tenant_id or PLATFORM_AUDIT_TENANT_ID, user_id=_ACTOR)
    async for session in database.open_session(tenant_id=tenant_id):
        uow = SqlAlchemyUnitOfWork(session, context)
        async with uow:
            yield uow


def _abort_for(database: Database) -> Callable[[uuid.UUID], Awaitable[None]]:
    async def _abort(tenant_id: uuid.UUID) -> None:
        async with _platform_uow(database, tenant_id) as uow:
            await CloseTenantUseCase(
                SqlAlchemyTenantRepository(uow),  # type: ignore[arg-type]
                _NoopStatusChecker(),
                uow,
            ).execute(CloseTenantCommand(tenant_id=tenant_id))

    return _abort


async def _provision(
    database: Database,
    command: ProvisionTenantCommand,
    *,
    email_sender: object | None = None,
) -> ProvisionedTenant:
    sender = email_sender or _RecordingEmailSender()

    def _invite_for(tenant_id: uuid.UUID) -> InviteStaffUserUseCase:
        return InviteStaffUserUseCase(
            SqlAlchemyStaffUserRepository(database, tenant_id),
            SqlAlchemyPasswordResetTokenRepository(database),
            Sha256TokenHasher(),
            sender,  # type: ignore[arg-type]
            reset_token_ttl=timedelta(hours=1),
        )

    async with _platform_uow(database) as uow:
        return await ProvisionTenantUseCase(
            SqlAlchemyTenantRepository(uow),  # type: ignore[arg-type]
            uow,
            SqlAlchemyIdentityUserRepository(database),
            _invite_for,
            _abort_for(database),
        ).execute(command)


def _command(**overrides: str) -> ProvisionTenantCommand:
    suffix = uuid.uuid4().hex[:10]
    fields = {
        "name": "Provisioning Test Agency",
        "slug": f"prov-{suffix}",
        "primary_contact_email": f"ops-{suffix}@prov.example",
        "admin_email": f"admin-{suffix}@prov.example",
    }
    fields.update(overrides)
    return ProvisionTenantCommand(**fields)


async def _scalar(admin_engine: AsyncEngine, sql: str, **params: object) -> object:
    async with admin_engine.connect() as conn:
        return (await conn.execute(text(sql), params)).scalar()


class TestProvisioning:
    async def test_creates_a_trial_tenant_and_a_ready_to_use_first_admin(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        command = _command()

        result = await _provision(database, command)

        # The tenant row got past RLS via the SECURITY DEFINER function.
        assert (
            await _scalar(
                admin_engine,
                "SELECT status FROM tenant.tenant WHERE id = :id",
                id=result.tenant.id,
            )
            == "trial"
        )
        # ... and is visible in the platform-wide listing.
        async with _platform_uow(database) as uow:
            listed = await ListTenantsUseCase(
                SqlAlchemyTenantRepository(uow)  # type: ignore[arg-type]
            ).execute(ListTenantsQuery())
        assert result.tenant.id in {t.id for t in listed}

        # The first admin belongs to the new tenant with the right role.
        assert (
            await _scalar(
                admin_engine,
                "SELECT role FROM identity.identity_user WHERE id = :id AND tenant_id = :t",
                id=result.admin.id,
                t=result.tenant.id,
            )
            == "agency_admin"
        )
        # Permissions were materialised — without them login works but every
        # permission check is a 403.
        granted = await _scalar(
            admin_engine,
            "SELECT count(*) FROM identity.identity_user_permission WHERE user_id = :id",
            id=result.admin.id,
        )
        assert isinstance(granted, int)
        assert granted > 0

    async def test_stores_only_the_hash_of_the_setup_token(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        result = await _provision(database, _command())

        stored = await _scalar(
            admin_engine,
            "SELECT token_hash FROM identity.password_reset_token WHERE user_id = :id",
            id=result.admin.id,
        )

        assert stored == Sha256TokenHasher().hash(result.setup_token)
        assert stored != result.setup_token

    async def test_writes_a_platform_audit_row_attributed_to_the_actor(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        result = await _provision(database, _command())

        async with admin_engine.connect() as conn:
            row = (
                await conn.execute(
                    text(
                        "SELECT action, tenant_id, actor_id, after_state->>'slug' AS slug "
                        "FROM audit.audit_log "
                        "WHERE entity_name = 'tenant' AND entity_id = :id"
                    ),
                    {"id": str(result.tenant.id)},
                )
            ).one()

        assert row.action == "create"
        assert row.tenant_id == PLATFORM_AUDIT_TENANT_ID
        assert row.actor_id == _ACTOR
        assert row.slug == result.tenant.slug


class TestConflicts:
    async def test_a_taken_slug_is_a_conflict_and_creates_no_second_admin(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        first = _command()
        await _provision(database, first)
        second = _command(slug=first.slug)

        with pytest.raises(ConflictError, match="already in use"):
            await _provision(database, second)

        assert (
            await _scalar(
                admin_engine,
                "SELECT count(*) FROM identity.identity_user WHERE email = :e",
                e=second.admin_email,
            )
            == 0
        )

    async def test_a_taken_admin_email_is_a_conflict_and_creates_no_tenant(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        first = _command()
        await _provision(database, first)
        second = _command(admin_email=first.admin_email)

        with pytest.raises(ConflictError, match="already exists"):
            await _provision(database, second)

        assert (
            await _scalar(
                admin_engine,
                "SELECT count(*) FROM tenant.tenant WHERE slug = :s",
                s=second.slug,
            )
            == 0
        )


class TestCompensation:
    async def test_a_failed_invite_closes_the_half_created_tenant(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        command = _command()

        with pytest.raises(RuntimeError, match="smtp exploded"):
            await _provision(database, command, email_sender=_FailingEmailSender())

        assert (
            await _scalar(
                admin_engine,
                "SELECT status FROM tenant.tenant WHERE slug = :s",
                s=command.slug,
            )
            == "closed"
        )
