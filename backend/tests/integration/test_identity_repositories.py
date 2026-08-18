"""Identity repositories, against real PostgreSQL — never mocked.

Proves the `SECURITY DEFINER` auth-bootstrap functions
(`migrations/versions/fa52b77ec442_*.py`, `10a62de534be_*.py`) actually work
end to end through the repository layer, connecting as the real,
non-superuser `lpg_app` role with **no tenant context set** — the exact
condition login/OTP/refresh/reset requests are in before authentication
succeeds. Seed data is created via the elevated `lpg_admin` role, the same
pattern `tests/tenant_isolation/test_tenant_rls.py` uses.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text

from lpg.domain.identity.password_reset_token import PasswordResetToken
from lpg.domain.identity.refresh_token import RefreshToken
from lpg.infrastructure.persistence.database import Database
from lpg.infrastructure.persistence.repositories.identity import (
    SqlAlchemyIdentityUserRepository,
    SqlAlchemyPasswordResetTokenRepository,
    SqlAlchemyPermissionRepository,
    SqlAlchemyRefreshTokenRepository,
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
                    "INSERT INTO tenant.tenant (id, name, slug) "
                    "VALUES (gen_random_uuid(), 'Identity Repo Test', :slug) RETURNING id"
                ),
                {"slug": f"identity-repo-{uuid.uuid4().hex[:10]}"},
            )
        ).scalar_one()
    return uuid.UUID(str(tenant_id))


async def _seed_user(
    admin_engine: AsyncEngine,
    tenant_id: uuid.UUID,
    *,
    email: str | None = None,
    phone_number: str | None = None,
    role: str = "manager",
) -> uuid.UUID:
    async with admin_engine.begin() as conn:
        user_id = (
            await conn.execute(
                text(
                    "INSERT INTO identity.identity_user "
                    "(id, tenant_id, email, phone_number, password_hash, role) "
                    "VALUES (gen_random_uuid(), :tenant_id, :email, :phone, 'seed-hash', :role) "
                    "RETURNING id"
                ),
                {"tenant_id": str(tenant_id), "email": email, "phone": phone_number, "role": role},
            )
        ).scalar_one()
        await conn.execute(
            text(
                "INSERT INTO identity.identity_user_permission (id, user_id, permission_id, created_at) "
                "SELECT gen_random_uuid(), :user_id, rp.permission_id, now() "
                "FROM identity.role_permission rp "
                "JOIN identity.role r ON r.id = rp.role_id "
                "WHERE r.code = :role"
            ),
            {"user_id": user_id, "role": role},
        )
    return uuid.UUID(str(user_id))


class TestSqlAlchemyIdentityUserRepository:
    async def test_get_by_email_finds_a_seeded_user(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        tenant_id = await _seed_tenant(admin_engine)
        email = f"{uuid.uuid4().hex[:10]}@example.com"
        await _seed_user(admin_engine, tenant_id, email=email)
        repo = SqlAlchemyIdentityUserRepository(database)

        user = await repo.get_by_email(email)

        assert user is not None
        assert user.email == email
        assert user.tenant_id == tenant_id

    async def test_get_by_email_returns_none_for_no_match(self, database: Database) -> None:
        repo = SqlAlchemyIdentityUserRepository(database)

        user = await repo.get_by_email(f"{uuid.uuid4().hex}@nowhere.example.com")

        assert user is None

    async def test_get_by_phone_number_is_scoped_to_tenant(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        tenant_a = await _seed_tenant(admin_engine)
        tenant_b = await _seed_tenant(admin_engine)
        phone = f"+1555{uuid.uuid4().int % 10_000_000:07d}"
        await _seed_user(admin_engine, tenant_a, phone_number=phone, role="customer")
        repo = SqlAlchemyIdentityUserRepository(database)

        found_in_own_tenant = await repo.get_by_phone_number(tenant_a, phone)
        found_in_other_tenant = await repo.get_by_phone_number(tenant_b, phone)

        assert found_in_own_tenant is not None
        assert found_in_other_tenant is None

    async def test_get_by_id_finds_a_seeded_user(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        tenant_id = await _seed_tenant(admin_engine)
        user_id = await _seed_user(admin_engine, tenant_id, email=f"{uuid.uuid4().hex}@x.example")
        repo = SqlAlchemyIdentityUserRepository(database)

        user = await repo.get(user_id)

        assert user is not None
        assert user.id == user_id

    async def test_save_persists_auth_state_changes(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        tenant_id = await _seed_tenant(admin_engine)
        email = f"{uuid.uuid4().hex}@x.example"
        await _seed_user(admin_engine, tenant_id, email=email)
        repo = SqlAlchemyIdentityUserRepository(database)
        user = await repo.get_by_email(email)
        assert user is not None

        user.record_failed_login(
            reason="bad_password", lockout_threshold=5, lockout_duration=timedelta(minutes=15)
        )
        await repo.save(user)

        reloaded = await repo.get_by_email(email)
        assert reloaded is not None
        assert reloaded.failed_login_count == 1


class TestSqlAlchemyRefreshTokenRepository:
    async def test_save_then_get_by_token_hash_round_trips(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        tenant_id = await _seed_tenant(admin_engine)
        user_id = await _seed_user(admin_engine, tenant_id, email=f"{uuid.uuid4().hex}@x.example")
        repo = SqlAlchemyRefreshTokenRepository(database)
        now = datetime.now(UTC)
        token = RefreshToken(
            uuid.uuid4(),
            user_id=user_id,
            token_hash=uuid.uuid4().hex,
            issued_at=now,
            expires_at=now + timedelta(days=30),
        )

        await repo.save(token)
        found = await repo.get_by_token_hash(token.token_hash)

        assert found is not None
        assert found.user_id == user_id

    async def test_get_by_token_hash_returns_none_for_no_match(self, database: Database) -> None:
        repo = SqlAlchemyRefreshTokenRepository(database)

        found = await repo.get_by_token_hash(uuid.uuid4().hex)

        assert found is None

    async def test_save_persists_rotation(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        tenant_id = await _seed_tenant(admin_engine)
        user_id = await _seed_user(admin_engine, tenant_id, email=f"{uuid.uuid4().hex}@x.example")
        repo = SqlAlchemyRefreshTokenRepository(database)
        now = datetime.now(UTC)
        token = RefreshToken(
            uuid.uuid4(),
            user_id=user_id,
            token_hash=uuid.uuid4().hex,
            issued_at=now,
            expires_at=now + timedelta(days=30),
        )
        await repo.save(token)

        replacement_id = uuid.uuid4()
        token.rotate(replacement_id)
        await repo.save(token)

        reloaded = await repo.get_by_token_hash(token.token_hash)
        assert reloaded is not None
        assert reloaded.rotated_at is not None
        assert reloaded.replaced_by_id == replacement_id

    async def test_revoke_all_for_user_revokes_every_active_token(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        tenant_id = await _seed_tenant(admin_engine)
        user_id = await _seed_user(admin_engine, tenant_id, email=f"{uuid.uuid4().hex}@x.example")
        repo = SqlAlchemyRefreshTokenRepository(database)
        now = datetime.now(UTC)
        tokens = [
            RefreshToken(
                uuid.uuid4(),
                user_id=user_id,
                token_hash=uuid.uuid4().hex,
                issued_at=now,
                expires_at=now + timedelta(days=30),
            )
            for _ in range(2)
        ]
        for token in tokens:
            await repo.save(token)

        await repo.revoke_all_for_user(user_id)

        for token in tokens:
            reloaded = await repo.get_by_token_hash(token.token_hash)
            assert reloaded is not None
            assert reloaded.revoked_at is not None


class TestSqlAlchemyPasswordResetTokenRepository:
    async def test_save_then_get_by_token_hash_round_trips(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        tenant_id = await _seed_tenant(admin_engine)
        user_id = await _seed_user(admin_engine, tenant_id, email=f"{uuid.uuid4().hex}@x.example")
        repo = SqlAlchemyPasswordResetTokenRepository(database)
        token = PasswordResetToken(
            uuid.uuid4(),
            user_id=user_id,
            token_hash=uuid.uuid4().hex,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )

        await repo.save(token)
        found = await repo.get_by_token_hash(token.token_hash)

        assert found is not None
        assert found.user_id == user_id
        assert found.is_usable()

    async def test_save_persists_mark_used(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        tenant_id = await _seed_tenant(admin_engine)
        user_id = await _seed_user(admin_engine, tenant_id, email=f"{uuid.uuid4().hex}@x.example")
        repo = SqlAlchemyPasswordResetTokenRepository(database)
        token = PasswordResetToken(
            uuid.uuid4(),
            user_id=user_id,
            token_hash=uuid.uuid4().hex,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
        await repo.save(token)

        token.mark_used()
        await repo.save(token)

        reloaded = await repo.get_by_token_hash(token.token_hash)
        assert reloaded is not None
        assert not reloaded.is_usable()


class TestSqlAlchemyPermissionRepository:
    async def test_has_permission_true_for_a_granted_permission(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        tenant_id = await _seed_tenant(admin_engine)
        user_id = await _seed_user(admin_engine, tenant_id, "granted@example.com")
        
        async with admin_engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO identity.identity_user_permission (id, user_id, permission_id) "
                    "SELECT gen_random_uuid(), :user_id, id FROM identity.permission WHERE code = 'tenant:configure'"
                ),
                {"user_id": user_id},
            )

        repo = SqlAlchemyPermissionRepository(database)
        assert await repo.has_permission(user_id=user_id, permission_code="tenant:configure")

    async def test_has_permission_false_for_an_ungranted_permission(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        tenant_id = await _seed_tenant(admin_engine)
        user_id = await _seed_user(admin_engine, tenant_id, "ungranted@example.com")
        
        repo = SqlAlchemyPermissionRepository(database)
        assert not await repo.has_permission(user_id=user_id, permission_code="tenant:configure")


class TestNoRlsBypassForDirectTableAccess:
    """The negative-control proof: without going through a SECURITY DEFINER
    function, `lpg_app` genuinely cannot read `identity_user` with no tenant
    context set — confirming the bootstrap functions are a deliberate,
    narrow exception, not evidence RLS silently isn't applied at all here.
    """

    async def test_direct_select_sees_nothing_without_tenant_context(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        tenant_id = await _seed_tenant(admin_engine)
        email = f"{uuid.uuid4().hex}@x.example"
        await _seed_user(admin_engine, tenant_id, email=email)

        async for session in database.session():
            result = await session.execute(
                text("SELECT 1 FROM identity.identity_user WHERE email = :email"),
                {"email": email},
            )
            assert result.first() is None
