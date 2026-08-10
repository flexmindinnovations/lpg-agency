"""`SqlAlchemyStaffUserRepository`, plus `InviteStaffUserUseCase` ->
`ConfirmPasswordResetUseCase` end-to-end — proving the reused
password-reset path actually activates an invited account, against a real
PostgreSQL.
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text

from lpg.application.common.errors import NotFoundError
from lpg.application.identity.password_reset import (
    ConfirmPasswordResetCommand,
    ConfirmPasswordResetUseCase,
)
from lpg.application.identity.staff_user import (
    DeactivateStaffUserCommand,
    DeactivateStaffUserUseCase,
    InviteStaffUserCommand,
    InviteStaffUserUseCase,
    ListStaffUsersQuery,
    ListStaffUsersUseCase,
    ReassignRoleCommand,
    ReassignRoleUseCase,
)
from lpg.infrastructure.identity.password_hasher import Argon2PasswordHasher
from lpg.infrastructure.identity.token_hasher import Sha256TokenHasher
from lpg.infrastructure.persistence.database import Database
from lpg.infrastructure.persistence.repositories.identity import (
    SqlAlchemyIdentityUserRepository,
    SqlAlchemyPasswordResetTokenRepository,
    SqlAlchemyRefreshTokenRepository,
    SqlAlchemyStaffUserRepository,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from sqlalchemy.ext.asyncio import AsyncEngine

    from lpg.config.settings import Settings

pytestmark = pytest.mark.integration


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


async def _seed_tenant(admin_engine: AsyncEngine) -> uuid.UUID:
    async with admin_engine.begin() as conn:
        tenant_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.tenant (id, name, slug, primary_contact_email) "
                    "VALUES (gen_random_uuid(), 'Staff Test Co', :slug, 'ops@example.com') "
                    "RETURNING id"
                ),
                {"slug": f"staff-test-{uuid.uuid4().hex[:10]}"},
            )
        ).scalar_one()
    return uuid.UUID(str(tenant_id))


class _StubEmailSender:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str, str]] = []

    async def send(self, to: str, subject: str, body: str) -> None:
        self.sent.append((to, subject, body))


class TestInviteStaffUserFlow:
    async def test_an_invited_user_can_activate_via_the_reused_reset_password_flow(
        self, database: Database, admin_engine: AsyncEngine, integration_settings: Settings
    ) -> None:
        tenant_id = await _seed_tenant(admin_engine)
        email = f"{uuid.uuid4().hex}@invite.example"
        token_hasher = Sha256TokenHasher()
        email_sender = _StubEmailSender()

        invite_use_case = InviteStaffUserUseCase(
            SqlAlchemyStaffUserRepository(database, tenant_id),
            SqlAlchemyPasswordResetTokenRepository(database),
            token_hasher,
            email_sender,
            reset_token_ttl=timedelta(hours=1),
        )
        invited = await invite_use_case.execute(
            InviteStaffUserCommand(tenant_id=tenant_id, email=email, role="manager")
        )
        assert invited.password_hash is None
        assert invited.is_active is True
        assert len(email_sender.sent) == 1
        _to, _subject, body = email_sender.sent[0]
        raw_token = body.rsplit("token=", 1)[1]

        hasher = Argon2PasswordHasher(integration_settings)
        # `ConfirmPasswordResetUseCase` is itself an unauthenticated flow —
        # the invited user follows the link with no tenant context resolved
        # yet, exactly like the original password-reset flow it's reused
        # from — so it uses the existing auth-bootstrap
        # `SqlAlchemyIdentityUserRepository` (`SECURITY DEFINER`-backed),
        # not the tenant-scoped `SqlAlchemyStaffUserRepository` an admin's
        # own authenticated requests use.
        confirm_use_case = ConfirmPasswordResetUseCase(
            SqlAlchemyPasswordResetTokenRepository(database),
            SqlAlchemyIdentityUserRepository(database),
            token_hasher,
            hasher,
        )
        await confirm_use_case.execute(
            ConfirmPasswordResetCommand(reset_token=raw_token, new_password="new-password-123")
        )

        activated = await SqlAlchemyStaffUserRepository(database, tenant_id).get(invited.id)
        assert activated is not None
        assert activated.password_hash is not None
        assert hasher.verify("new-password-123", activated.password_hash)


class TestDeactivateStaffUser:
    async def test_deactivating_revokes_every_outstanding_refresh_token(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        tenant_id = await _seed_tenant(admin_engine)
        email = f"{uuid.uuid4().hex}@deactivate.example"
        repository = SqlAlchemyStaffUserRepository(database, tenant_id)

        invite_use_case = InviteStaffUserUseCase(
            repository,
            SqlAlchemyPasswordResetTokenRepository(database),
            Sha256TokenHasher(),
            _StubEmailSender(),
            reset_token_ttl=timedelta(hours=1),
        )
        invited = await invite_use_case.execute(
            InviteStaffUserCommand(tenant_id=tenant_id, email=email, role="dispatcher")
        )

        refresh_token_repository = SqlAlchemyRefreshTokenRepository(database)
        deactivate_use_case = DeactivateStaffUserUseCase(repository, refresh_token_repository)
        await deactivate_use_case.execute(DeactivateStaffUserCommand(user_id=invited.id))

        reloaded = await repository.get(invited.id)
        assert reloaded is not None
        assert reloaded.is_active is False

    async def test_deactivating_an_unknown_user_raises_not_found(self, database: Database) -> None:
        repository = SqlAlchemyStaffUserRepository(database, uuid.uuid4())
        use_case = DeactivateStaffUserUseCase(
            repository, SqlAlchemyRefreshTokenRepository(database)
        )

        with pytest.raises(NotFoundError):
            await use_case.execute(DeactivateStaffUserCommand(user_id=uuid.uuid4()))


class TestReassignRole:
    async def test_changes_the_role(self, database: Database, admin_engine: AsyncEngine) -> None:
        tenant_id = await _seed_tenant(admin_engine)
        email = f"{uuid.uuid4().hex}@reassign.example"
        repository = SqlAlchemyStaffUserRepository(database, tenant_id)

        invite_use_case = InviteStaffUserUseCase(
            repository,
            SqlAlchemyPasswordResetTokenRepository(database),
            Sha256TokenHasher(),
            _StubEmailSender(),
            reset_token_ttl=timedelta(hours=1),
        )
        invited = await invite_use_case.execute(
            InviteStaffUserCommand(tenant_id=tenant_id, email=email, role="manager")
        )

        reassign_use_case = ReassignRoleUseCase(repository)
        await reassign_use_case.execute(
            ReassignRoleCommand(user_id=invited.id, new_role="accountant")
        )

        reloaded = await repository.get(invited.id)
        assert reloaded is not None
        assert reloaded.role == "accountant"


class TestListStaffUsers:
    async def test_excludes_customer_and_driver_roles(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        tenant_id = await _seed_tenant(admin_engine)
        repository = SqlAlchemyStaffUserRepository(database, tenant_id)
        invite_use_case = InviteStaffUserUseCase(
            repository,
            SqlAlchemyPasswordResetTokenRepository(database),
            Sha256TokenHasher(),
            _StubEmailSender(),
            reset_token_ttl=timedelta(hours=1),
        )
        await invite_use_case.execute(
            InviteStaffUserCommand(
                tenant_id=tenant_id, email=f"{uuid.uuid4().hex}@staff.example", role="manager"
            )
        )
        async with admin_engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO identity.identity_user (id, tenant_id, phone_number, role) "
                    "VALUES (gen_random_uuid(), :tenant_id, :phone, 'customer')"
                ),
                {"tenant_id": str(tenant_id), "phone": f"+1555{uuid.uuid4().int % 10_000_000:07d}"},
            )

        list_use_case = ListStaffUsersUseCase(repository)
        staff = await list_use_case.execute(ListStaffUsersQuery(tenant_id=tenant_id))

        assert len(staff) == 1
        assert staff[0].role == "manager"
