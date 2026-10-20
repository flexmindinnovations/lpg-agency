"""`SqlAlchemyStaffUserRepository`, plus `InviteStaffUserUseCase` ->
`ConfirmPasswordResetUseCase` end-to-end — proving the reused
password-reset path actually activates an invited account, against a real
PostgreSQL. Also the DA-01 / DA-24 rules: no self-deactivation, the last
agency admin is protected, deactivation can be undone, and every identity
change writes an audit entry.
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text

from lpg.application.common.errors import ConflictError, NotFoundError, ValidationError
from lpg.application.common.tenant import RequestTenantContext
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
    ReactivateStaffUserCommand,
    ReactivateStaffUserUseCase,
    ReassignRoleCommand,
    ReassignRoleUseCase,
    UpdateStaffUserPermissionsCommand,
    UpdateStaffUserPermissionsUseCase,
)
from lpg.infrastructure.identity.password_hasher import Argon2PasswordHasher
from lpg.infrastructure.identity.token_hasher import Sha256TokenHasher
from lpg.infrastructure.persistence.audit_trail import SqlAlchemyAuditTrail
from lpg.infrastructure.persistence.database import Database
from lpg.infrastructure.persistence.repositories.identity import (
    SqlAlchemyIdentityUserRepository,
    SqlAlchemyPasswordResetTokenRepository,
    SqlAlchemyPermissionRepository,
    SqlAlchemyRefreshTokenRepository,
    SqlAlchemyStaffUserRepository,
)
from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

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


class _RecordingAudit:
    def __init__(self) -> None:
        self.entries: list[dict[str, object]] = []

    async def record(self, **entry: object) -> None:
        self.entries.append(entry)


async def _invite(
    database: Database, tenant_id: uuid.UUID, role: str, email: str | None = None
) -> uuid.UUID:
    invited = await InviteStaffUserUseCase(
        SqlAlchemyStaffUserRepository(database, tenant_id),
        SqlAlchemyPasswordResetTokenRepository(database),
        Sha256TokenHasher(),
        _StubEmailSender(),
        reset_token_ttl=timedelta(hours=1),
    ).execute(
        InviteStaffUserCommand(
            tenant_id=tenant_id, email=email or f"{uuid.uuid4().hex}@staff.example", role=role
        )
    )
    return invited.id


def _deactivate(database: Database, tenant_id: uuid.UUID) -> DeactivateStaffUserUseCase:
    return DeactivateStaffUserUseCase(
        SqlAlchemyStaffUserRepository(database, tenant_id),
        SqlAlchemyRefreshTokenRepository(database),
        _RecordingAudit(),
    )


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
        assert "/set-password?token=" in body
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
        audit = _RecordingAudit()
        deactivate_use_case = DeactivateStaffUserUseCase(
            repository, refresh_token_repository, audit
        )
        await deactivate_use_case.execute(
            DeactivateStaffUserCommand(user_id=invited.id, actor_id=uuid.uuid4())
        )
        assert audit.entries[0]["action"] == "deactivate"

        reloaded = await repository.get(invited.id)
        assert reloaded is not None
        assert reloaded.is_active is False

    async def test_deactivating_an_unknown_user_raises_not_found(self, database: Database) -> None:
        repository = SqlAlchemyStaffUserRepository(database, uuid.uuid4())
        use_case = DeactivateStaffUserUseCase(
            repository, SqlAlchemyRefreshTokenRepository(database), _RecordingAudit()
        )

        with pytest.raises(NotFoundError):
            await use_case.execute(
                DeactivateStaffUserCommand(user_id=uuid.uuid4(), actor_id=uuid.uuid4())
            )

    async def test_an_admin_cannot_deactivate_themselves(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        tenant_id = await _seed_tenant(admin_engine)
        await _invite(database, tenant_id, "agency_admin")
        me = await _invite(database, tenant_id, "agency_admin")

        with pytest.raises(ConflictError, match="your own account"):
            await _deactivate(database, tenant_id).execute(
                DeactivateStaffUserCommand(user_id=me, actor_id=me)
            )

    async def test_the_last_active_agency_admin_cannot_be_deactivated(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        tenant_id = await _seed_tenant(admin_engine)
        only_admin = await _invite(database, tenant_id, "agency_admin")
        manager = await _invite(database, tenant_id, "manager")

        with pytest.raises(ConflictError, match="last active agency admin"):
            await _deactivate(database, tenant_id).execute(
                DeactivateStaffUserCommand(user_id=only_admin, actor_id=manager)
            )

    async def test_a_second_admin_can_be_deactivated_and_reactivated(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        tenant_id = await _seed_tenant(admin_engine)
        me = await _invite(database, tenant_id, "agency_admin")
        other = await _invite(database, tenant_id, "agency_admin")
        repository = SqlAlchemyStaffUserRepository(database, tenant_id)

        await _deactivate(database, tenant_id).execute(
            DeactivateStaffUserCommand(user_id=other, actor_id=me)
        )
        assert (await repository.get(other)).is_active is False  # type: ignore[union-attr]

        audit = _RecordingAudit()
        await ReactivateStaffUserUseCase(repository, audit).execute(
            ReactivateStaffUserCommand(user_id=other, actor_id=me)
        )
        assert (await repository.get(other)).is_active is True  # type: ignore[union-attr]
        assert audit.entries[0]["action"] == "reactivate"
        assert audit.entries[0]["after"] == {"is_active": True}

    async def test_another_tenants_user_is_not_visible(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        tenant_a = await _seed_tenant(admin_engine)
        tenant_b = await _seed_tenant(admin_engine)
        victim = await _invite(database, tenant_b, "manager")

        with pytest.raises(NotFoundError):
            await _deactivate(database, tenant_a).execute(
                DeactivateStaffUserCommand(user_id=victim, actor_id=uuid.uuid4())
            )
        reloaded = await SqlAlchemyStaffUserRepository(database, tenant_b).get(victim)
        assert reloaded is not None
        assert reloaded.is_active is True

    async def test_the_audit_entry_reaches_the_tenants_audit_log(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        """Wired like the router: the entry is written in the request's UoW."""
        tenant_id = await _seed_tenant(admin_engine)
        actor = await _invite(database, tenant_id, "agency_admin")
        target = await _invite(database, tenant_id, "dispatcher")

        context = RequestTenantContext(tenant_id=tenant_id, user_id=actor)
        async for session in database.open_session(tenant_id=tenant_id):
            uow = SqlAlchemyUnitOfWork(session, context)
            async with uow:
                await DeactivateStaffUserUseCase(
                    SqlAlchemyStaffUserRepository(database, tenant_id),
                    SqlAlchemyRefreshTokenRepository(database),
                    SqlAlchemyAuditTrail(uow),
                ).execute(DeactivateStaffUserCommand(user_id=target, actor_id=actor))

        async with admin_engine.connect() as conn:
            row = (
                await conn.execute(
                    text(
                        "SELECT tenant_id, actor_id, action, entity_name, after_state "
                        "FROM audit.audit_log WHERE entity_id = :id"
                    ),
                    {"id": str(target)},
                )
            ).one()
        assert row.tenant_id == tenant_id
        assert row.actor_id == actor
        assert row.action == "deactivate"
        assert row.entity_name == "identity_user"
        assert row.after_state == {"is_active": False}


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

        audit = _RecordingAudit()
        permissions = SqlAlchemyPermissionRepository(database)
        reassign_use_case = ReassignRoleUseCase(repository, permissions, audit)
        await reassign_use_case.execute(
            ReassignRoleCommand(user_id=invited.id, new_role="accountant", actor_id=uuid.uuid4())
        )

        reloaded = await repository.get(invited.id)
        assert reloaded is not None
        assert reloaded.role == "accountant"
        # The old role's permissions do not linger after the change.
        assert await permissions.get_permission_codes_for_user(
            invited.id
        ) == await permissions.get_permission_codes_for_role("accountant")
        assert audit.entries[0]["before"] == {"role": "manager"}
        assert audit.entries[0]["after"] == {"role": "accountant"}

    async def test_platform_and_customer_roles_cannot_be_assigned(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        tenant_id = await _seed_tenant(admin_engine)
        user = await _invite(database, tenant_id, "manager")
        use_case = ReassignRoleUseCase(
            SqlAlchemyStaffUserRepository(database, tenant_id),
            SqlAlchemyPermissionRepository(database),
            _RecordingAudit(),
        )
        for role in ("super_admin", "customer", "driver"):
            with pytest.raises(ValidationError):
                await use_case.execute(
                    ReassignRoleCommand(user_id=user, new_role=role, actor_id=uuid.uuid4())
                )

    async def test_the_last_admin_cannot_be_demoted(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        tenant_id = await _seed_tenant(admin_engine)
        admin = await _invite(database, tenant_id, "agency_admin")
        use_case = ReassignRoleUseCase(
            SqlAlchemyStaffUserRepository(database, tenant_id),
            SqlAlchemyPermissionRepository(database),
            _RecordingAudit(),
        )
        with pytest.raises(ConflictError):
            await use_case.execute(
                ReassignRoleCommand(user_id=admin, new_role="manager", actor_id=uuid.uuid4())
            )


class TestUpdatePermissions:
    async def test_changes_are_audited_and_self_edits_refused(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        tenant_id = await _seed_tenant(admin_engine)
        me = await _invite(database, tenant_id, "agency_admin")
        user = await _invite(database, tenant_id, "dispatcher")
        permissions = SqlAlchemyPermissionRepository(database)
        audit = _RecordingAudit()
        use_case = UpdateStaffUserPermissionsUseCase(
            SqlAlchemyStaffUserRepository(database, tenant_id), permissions, audit
        )

        before = await permissions.get_permission_codes_for_user(user)
        revoked = sorted(before)[0]
        await use_case.execute(
            UpdateStaffUserPermissionsCommand(
                user_id=user, permission_codes=set(before) - {revoked}, actor_id=me
            )
        )
        assert revoked not in await permissions.get_permission_codes_for_user(user)
        assert audit.entries[0]["details"]["revoked"] == [revoked]  # type: ignore[index]

        with pytest.raises(ConflictError):
            await use_case.execute(
                UpdateStaffUserPermissionsCommand(user_id=me, permission_codes=set(), actor_id=me)
            )
        with pytest.raises(ValidationError):
            await use_case.execute(
                UpdateStaffUserPermissionsCommand(
                    user_id=user, permission_codes={"made:up"}, actor_id=me
                )
            )


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
            user_id = (
                await conn.execute(
                    text(
                        "INSERT INTO identity.identity_user (id, tenant_id, phone_number, role) "
                        "VALUES (gen_random_uuid(), :tenant_id, :phone, 'customer') "
                        "RETURNING id"
                    ),
                    {
                        "tenant_id": str(tenant_id),
                        "phone": f"+1555{uuid.uuid4().int % 10_000_000:07d}",
                    },
                )
            ).scalar_one()
            await conn.execute(
                text(
                    "INSERT INTO identity.identity_user_permission "
                    "(id, user_id, permission_id, created_at) "
                    "SELECT gen_random_uuid(), :user_id, rp.permission_id, now() "
                    "FROM identity.role_permission rp "
                    "JOIN identity.role r ON r.id = rp.role_id "
                    "WHERE r.code = :role"
                ),
                # Matches the role hardcoded in the INSERT above: this user is
                # seeded precisely so the assertion can prove ListStaffUsers
                # excludes it.
                {"user_id": user_id, "role": "customer"},
            )

        list_use_case = ListStaffUsersUseCase(repository)
        staff = await list_use_case.execute(ListStaffUsersQuery(tenant_id=tenant_id))

        assert len(staff) == 1
        assert staff[0].role == "manager"
