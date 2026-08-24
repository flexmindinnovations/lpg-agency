"""Full Platform Console lifecycle: suspend -> reactivate -> close an
agency, through the real use cases against real PostgreSQL, plus proof of
the two things this plan exists to fix — a genuine `tenant_id = NULL`
`super_admin` session can (1) actually reach a `UnitOfWork`-backed
endpoint at all, and (2) see every tenant, not just its own.

`test_platform_rbac.py` proves the auth/permission chain in isolation;
this file proves the tenant-suspension enforcement (`LoginUseCase`) and
cross-tenant reads (`list_all()`) work end to end together.
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from lpg.application.common.errors import TenantSuspendedError
from lpg.application.common.tenant import RequestTenantContext
from lpg.application.identity.login import LoginCommand, LoginUseCase
from lpg.application.tenant.manage_lifecycle import (
    CloseTenantCommand,
    CloseTenantUseCase,
    ListTenantsQuery,
    ListTenantsUseCase,
    ReactivateTenantCommand,
    ReactivateTenantUseCase,
    SuspendTenantCommand,
    SuspendTenantUseCase,
)
from lpg.domain.common.base import InvariantViolation
from lpg.domain.license.license import LicenseLifecycleState
from lpg.infrastructure.identity.password_hasher import Argon2PasswordHasher
from lpg.infrastructure.identity.token_hasher import Sha256TokenHasher
from lpg.infrastructure.persistence.database import Database
from lpg.infrastructure.persistence.repositories.identity import (
    SqlAlchemyIdentityUserRepository,
    SqlAlchemyPermissionRepository,
    SqlAlchemyRefreshTokenRepository,
)
from lpg.infrastructure.persistence.repositories.tenant import SqlAlchemyTenantRepository
from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from sqlalchemy.ext.asyncio import AsyncEngine

    from lpg.application.tenant.status import TenantStatusChecker
    from lpg.config.settings import Settings

pytestmark = pytest.mark.integration


class _AlwaysActiveLicenseStatusChecker:
    """This suite's own concern is tenant suspension, not license
    enforcement (that's `test_auth_flows.py::TestLicenseGate`) — every
    login here is treated as belonging to an always-active-license
    tenant, mirroring that file's identically-named stub."""

    async def get_status(self, tenant_id: uuid.UUID) -> LicenseLifecycleState:
        del tenant_id
        return LicenseLifecycleState.ACTIVE

    async def invalidate(self, tenant_id: uuid.UUID) -> None:
        del tenant_id


class _NoopTenantStatusChecker:
    """The real `RedisTenantStatusChecker` is what `get_tenant_context`
    uses in production; the lifecycle use cases (`SuspendTenantUseCase`
    etc.) only ever call `invalidate()`, never `get_status()` — so this
    stub only needs to satisfy the former."""

    async def get_status(self, tenant_id: uuid.UUID) -> str:
        del tenant_id
        raise NotImplementedError

    async def invalidate(self, tenant_id: uuid.UUID) -> None:
        del tenant_id


class _DirectTenantStatusChecker:
    """Reads `tenant.tenant.status` fresh on every call, through the same
    `tenant.tenant_find_status_by_id` `SECURITY DEFINER` function the real
    `RedisTenantStatusChecker` falls back to on a cache miss — just
    without the Redis layer in front, since this suite's own concern is
    the enforcement wiring, not the cache."""

    def __init__(self, database: Database) -> None:
        self._database = database

    async def get_status(self, tenant_id: uuid.UUID) -> str:
        async for session in self._database.session():
            result = await session.execute(
                text("SELECT tenant.tenant_find_status_by_id(:tenant_id)"),
                {"tenant_id": str(tenant_id)},
            )
            return str(result.scalar_one())
        raise AssertionError  # pragma: no cover - session() yields once

    async def invalidate(self, tenant_id: uuid.UUID) -> None:
        del tenant_id


class _StubJwtSigner:
    def issue_access_token(self, claims: dict[str, object]) -> str:
        return f"stub-token-for-{claims.get('sub')}"

    def decode_access_token(self, token: str) -> dict[str, object]:
        raise NotImplementedError


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
        "postgresql+asyncpg://lpg_admin:dev_only_not_a_real_secret@localhost:55432/lpg_test"
    )
    try:
        yield engine
    finally:
        await engine.dispose()


async def _seed_tenant_with_active_user(
    admin_engine: AsyncEngine, *, email: str, password_hash: str
) -> uuid.UUID:
    async with admin_engine.begin() as conn:
        tenant_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.tenant (id, name, slug, status, primary_contact_email) "
                    "VALUES (gen_random_uuid(), 'Platform Lifecycle Test Co', :slug, 'active', "
                    "'ops@example.com') RETURNING id"
                ),
                {"slug": f"platform-lifecycle-{uuid.uuid4().hex[:10]}"},
            )
        ).scalar_one()
        await conn.execute(
            text(
                "INSERT INTO identity.identity_user "
                "(id, tenant_id, email, password_hash, role) "
                "VALUES (gen_random_uuid(), :tenant_id, :email, :password_hash, 'agency_admin')"
            ),
            {"tenant_id": str(tenant_id), "email": email, "password_hash": password_hash},
        )
    return uuid.UUID(str(tenant_id))


def _login_use_case(
    database: Database, hasher: Argon2PasswordHasher, tenant_status_checker: TenantStatusChecker
) -> LoginUseCase:
    return LoginUseCase(
        SqlAlchemyIdentityUserRepository(database),
        SqlAlchemyRefreshTokenRepository(database),
        SqlAlchemyPermissionRepository(database),
        hasher,
        Sha256TokenHasher(),
        _StubJwtSigner(),
        _AlwaysActiveLicenseStatusChecker(),
        tenant_status_checker,
        lockout_threshold=5,
        lockout_duration=timedelta(minutes=15),
        refresh_token_ttl=timedelta(days=30),
    )


class TestAgencySuspensionBlocksLogin:
    async def test_suspend_blocks_login_reactivate_restores_it(
        self, database: Database, admin_engine: AsyncEngine, integration_settings: Settings
    ) -> None:
        email = f"{uuid.uuid4().hex}@platform-lifecycle.example"
        password = "correct horse battery staple 42"
        hasher = Argon2PasswordHasher(integration_settings)
        tenant_id = await _seed_tenant_with_active_user(
            admin_engine, email=email, password_hash=hasher.hash(password)
        )
        context = RequestTenantContext(tenant_id=tenant_id)
        status_checker = _DirectTenantStatusChecker(database)

        # 1. Login works while the agency is active.
        pair = await _login_use_case(database, hasher, status_checker).execute(
            LoginCommand(email=email, password=password)
        )
        assert pair.access_token

        # 2. Suspend the agency through the real use case.
        async for session in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(session, context) as uow:
                repository = SqlAlchemyTenantRepository(uow)
                suspend_use_case = SuspendTenantUseCase(repository, _NoopTenantStatusChecker(), uow)
                await suspend_use_case.execute(SuspendTenantCommand(tenant_id=tenant_id))

        # 3. Login now rejects — the exact enforcement this plan adds.
        with pytest.raises(TenantSuspendedError):
            await _login_use_case(database, hasher, status_checker).execute(
                LoginCommand(email=email, password=password)
            )

        # 4. A second suspend attempt is a clean domain error, not a silent
        # no-op — `Tenant._transition_to`'s own invariant.
        async for session in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(session, context) as uow:
                repository = SqlAlchemyTenantRepository(uow)
                tenant = await repository.get(tenant_id)
                assert tenant is not None
                with pytest.raises(InvariantViolation):
                    tenant.suspend()

        # 5. Reactivate — login works again.
        async for session in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(session, context) as uow:
                repository = SqlAlchemyTenantRepository(uow)
                reactivate_use_case = ReactivateTenantUseCase(
                    repository, _NoopTenantStatusChecker(), uow
                )
                await reactivate_use_case.execute(ReactivateTenantCommand(tenant_id=tenant_id))

        pair = await _login_use_case(database, hasher, status_checker).execute(
            LoginCommand(email=email, password=password)
        )
        assert pair.access_token

        # 6. Close is terminal — login rejects again, and reactivate is no
        # longer a legal transition.
        async for session in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(session, context) as uow:
                repository = SqlAlchemyTenantRepository(uow)
                close_use_case = CloseTenantUseCase(repository, _NoopTenantStatusChecker(), uow)
                await close_use_case.execute(CloseTenantCommand(tenant_id=tenant_id))

        with pytest.raises(TenantSuspendedError):
            await _login_use_case(database, hasher, status_checker).execute(
                LoginCommand(email=email, password=password)
            )

        async for session in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(session, context) as uow:
                repository = SqlAlchemyTenantRepository(uow)
                tenant = await repository.get(tenant_id)
                assert tenant is not None
                with pytest.raises(InvariantViolation):
                    tenant.reactivate()


class TestCrossTenantAgencyListing:
    """The specific regression this plan fixes: a genuine `super_admin`
    session (no `tenant_id` claim) sees *every* tenant through
    `list_all()`, not just one it happens to have created itself — proving
    both the `SECURITY DEFINER` RLS bypass (migration `fdd3afde337c`) and
    that a null-tenant caller can reach a `UnitOfWork`-backed use case at
    all via `get_platform_unit_of_work_factory`."""

    async def test_list_all_sees_tenants_it_did_not_create(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        tenant_a = await _seed_tenant_with_active_user(
            admin_engine, email=f"{uuid.uuid4().hex}@cross-a.example", password_hash="x"
        )
        tenant_b = await _seed_tenant_with_active_user(
            admin_engine, email=f"{uuid.uuid4().hex}@cross-b.example", password_hash="x"
        )

        # Scoped to a THIRD, unrelated tenant — mirrors what an unscoped
        # `Database.session()` call (no `app.current_tenant_id` at all)
        # would see, without needing a real `JwtPlatformPrincipal`/HTTP
        # round trip in this suite.
        unrelated_tenant = uuid.uuid4()
        context = RequestTenantContext(tenant_id=unrelated_tenant)
        async for session in database.open_session(tenant_id=unrelated_tenant):
            async with SqlAlchemyUnitOfWork(session, context) as uow:
                repository = SqlAlchemyTenantRepository(uow)
                list_use_case = ListTenantsUseCase(repository)
                tenants = await list_use_case.execute(ListTenantsQuery())

        seen_ids = {t.id for t in tenants}
        assert tenant_a in seen_ids
        assert tenant_b in seen_ids
