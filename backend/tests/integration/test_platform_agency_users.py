"""Agency User Management (Phase 31) against real PostgreSQL.

Proves what unit tests cannot: that another agency's user is invisible through
row-level security (404, never a hint it exists), that issuing a fresh setup link
really kills the older ones in the database, that the hand-written audit entry is
accepted by `audit.audit_log`'s policy and attributed to the target agency, and
that no token ever reaches the audit trail.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from lpg.application.common.errors import ConflictError, NotFoundError
from lpg.application.identity.staff_user import InviteStaffUserUseCase
from lpg.application.platform.agency_users import (
    AGENCY_ADMIN_ROLE,
    AddAgencyAdminCommand,
    AddAgencyAdminUseCase,
    IssuedSetupLink,
    IssueSetupLinkCommand,
    IssueSetupLinkUseCase,
    ListAgencyUsersQuery,
    ListAgencyUsersUseCase,
)
from lpg.application.tenant.manage_lifecycle import CloseTenantCommand, CloseTenantUseCase
from lpg.infrastructure.identity.token_hasher import Sha256TokenHasher
from lpg.infrastructure.persistence.audit_trail import SqlAlchemyPlatformAuditTrail
from lpg.infrastructure.persistence.database import Database
from lpg.infrastructure.persistence.repositories.identity import (
    SqlAlchemyIdentityUserRepository,
    SqlAlchemyPasswordResetTokenRepository,
    SqlAlchemyStaffUserRepository,
)
from lpg.infrastructure.persistence.repositories.tenant import SqlAlchemyTenantRepository
from tests.integration.test_platform_agency_provisioning import (
    _ACTOR,
    _command,
    _NoopStatusChecker,
    _platform_uow,
    _provision,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from sqlalchemy.ext.asyncio import AsyncEngine

    from lpg.application.tenant.provision_tenant import ProvisionedTenant
    from lpg.config.settings import Settings

pytestmark = pytest.mark.integration

TTL = timedelta(hours=24)


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


class _SilentEmail:
    async def send(self, to: str, subject: str, body: str) -> None:
        del to, subject, body


async def _add_admin(database: Database, tenant_id: uuid.UUID, email: str) -> IssuedSetupLink:
    """Wired exactly like the `POST /platform/agencies/{id}/admins` route."""
    async with _platform_uow(database, tenant_id) as uow:
        invite = InviteStaffUserUseCase(
            SqlAlchemyStaffUserRepository(database, tenant_id),
            SqlAlchemyPasswordResetTokenRepository(database),
            Sha256TokenHasher(),
            _SilentEmail(),
            reset_token_ttl=TTL,
        )
        issued = await AddAgencyAdminUseCase(
            SqlAlchemyTenantRepository(uow),  # type: ignore[arg-type]
            SqlAlchemyIdentityUserRepository(database),
            invite,
            SqlAlchemyPlatformAuditTrail(uow),  # type: ignore[arg-type]
        ).execute(AddAgencyAdminCommand(tenant_id=tenant_id, email=email))
        await uow.commit()
    return issued


async def _issue_link(
    database: Database, tenant_id: uuid.UUID, user_id: uuid.UUID
) -> IssuedSetupLink:
    """Wired exactly like the `POST .../users/{user_id}/setup-link` route."""
    async with _platform_uow(database, tenant_id) as uow:
        issued = await IssueSetupLinkUseCase(
            SqlAlchemyTenantRepository(uow),  # type: ignore[arg-type]
            SqlAlchemyStaffUserRepository(database, tenant_id),
            SqlAlchemyPasswordResetTokenRepository(database),
            Sha256TokenHasher(),
            SqlAlchemyPlatformAuditTrail(uow),  # type: ignore[arg-type]
            link_ttl=TTL,
        ).execute(IssueSetupLinkCommand(tenant_id=tenant_id, user_id=user_id))
        await uow.commit()
    return issued


async def _new_agency(database: Database) -> ProvisionedTenant:
    return await _provision(database, _command())


async def _scalar(admin_engine: AsyncEngine, sql: str, **params: object) -> object:
    async with admin_engine.connect() as conn:
        return (await conn.execute(text(sql), params)).scalar()


class TestAddAgencyAdmin:
    async def test_adds_a_second_admin_with_permissions_and_a_24h_link(
        self,
        database: Database,
        admin_engine: AsyncEngine,
    ) -> None:
        agency = await _new_agency(database)
        email = f"second-{uuid.uuid4().hex[:8]}@prov.example"

        issued = await _add_admin(database, agency.tenant.id, email)

        assert issued.user.role == AGENCY_ADMIN_ROLE
        assert (
            await _scalar(
                admin_engine,
                "SELECT tenant_id FROM identity.identity_user WHERE id = :id",
                id=issued.user.id,
            )
            == agency.tenant.id
        )
        granted = await _scalar(
            admin_engine,
            "SELECT count(*) FROM identity.identity_user_permission WHERE user_id = :id",
            id=issued.user.id,
        )
        assert isinstance(granted, int)
        assert granted > 0
        remaining = issued.setup_token_expires_at - datetime.now(UTC)
        assert timedelta(hours=23) < remaining <= TTL

    async def test_lists_only_that_agencys_staff(
        self,
        database: Database,
    ) -> None:
        one, two = await _new_agency(database), await _new_agency(database)

        async with _platform_uow(database, one.tenant.id) as uow:
            users = await ListAgencyUsersUseCase(
                SqlAlchemyTenantRepository(uow),  # type: ignore[arg-type]
                SqlAlchemyStaffUserRepository(database, one.tenant.id),
            ).execute(ListAgencyUsersQuery(tenant_id=one.tenant.id))

        emails = {u.email for u in users}
        assert one.admin.email in emails
        assert two.admin.email not in emails

    async def test_a_taken_email_is_a_conflict(
        self,
        database: Database,
    ) -> None:
        agency = await _new_agency(database)

        with pytest.raises(ConflictError, match="already exists"):
            await _add_admin(database, agency.tenant.id, str(agency.admin.email))


class TestIssueSetupLink:
    async def test_a_new_link_kills_the_older_ones_and_is_itself_usable(
        self,
        database: Database,
    ) -> None:
        agency = await _new_agency(database)  # created with one link already
        hasher = Sha256TokenHasher()
        tokens = SqlAlchemyPasswordResetTokenRepository(database)
        first = await tokens.get_by_token_hash(hasher.hash(agency.setup_token))
        assert first is not None
        assert first.is_usable()

        issued = await _issue_link(database, agency.tenant.id, agency.admin.id)

        old = await tokens.get_by_token_hash(hasher.hash(agency.setup_token))
        new = await tokens.get_by_token_hash(hasher.hash(issued.setup_token))
        assert old is not None
        assert not old.is_usable()  # marked used the moment the new link existed
        assert new is not None
        assert new.is_usable()
        assert timedelta(hours=23) < new.expires_at - datetime.now(UTC) <= TTL

    async def test_another_agencys_user_is_not_found(
        self,
        database: Database,
    ) -> None:
        mine, theirs = await _new_agency(database), await _new_agency(database)

        with pytest.raises(NotFoundError):
            await _issue_link(database, mine.tenant.id, theirs.admin.id)

    async def test_a_closed_agency_is_refused(
        self,
        database: Database,
    ) -> None:
        agency = await _new_agency(database)
        async with _platform_uow(database, agency.tenant.id) as uow:
            await CloseTenantUseCase(
                SqlAlchemyTenantRepository(uow),  # type: ignore[arg-type]
                _NoopStatusChecker(),
                uow,
            ).execute(CloseTenantCommand(tenant_id=agency.tenant.id))

        with pytest.raises(ConflictError, match="closed"):
            await _issue_link(database, agency.tenant.id, agency.admin.id)


class TestAudit:
    async def test_both_actions_are_audited_against_the_target_agency_without_the_token(
        self,
        database: Database,
        admin_engine: AsyncEngine,
    ) -> None:
        agency = await _new_agency(database)
        added = await _add_admin(
            database, agency.tenant.id, f"audited-{uuid.uuid4().hex[:8]}@prov.example"
        )
        reissued = await _issue_link(database, agency.tenant.id, agency.admin.id)

        async with admin_engine.connect() as conn:
            rows = (
                await conn.execute(
                    text(
                        "SELECT action, tenant_id, actor_id, entity_id, "
                        "metadata::text AS meta "
                        "FROM audit.audit_log "
                        "WHERE tenant_id = :t AND action LIKE 'platform.%' "
                        "ORDER BY performed_at"
                    ),
                    {"t": agency.tenant.id},
                )
            ).all()

        assert [r.action for r in rows] == [
            "platform.agency_admin_added",
            "platform.setup_link_issued",
        ]
        assert all(r.tenant_id == agency.tenant.id for r in rows)  # visible to the agency
        assert all(r.actor_id == _ACTOR for r in rows)  # the Super Admin
        assert rows[0].entity_id == str(added.user.id)
        assert rows[1].entity_id == str(agency.admin.id)
        for row in rows:
            assert json.loads(row.meta)["agency"] == agency.tenant.slug
            assert added.setup_token not in row.meta
            assert reissued.setup_token not in row.meta
