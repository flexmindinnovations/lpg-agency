"""Issue -> activate -> revoke -> reissue -> reactivate, through the real use
cases against real PostgreSQL.

Covers the gap `f5746de5730e` (allow license reissuance after revoke) exists
to close: before it, `platform.license.tenant_id` was a plain UNIQUE column,
so revoking a tenant's license permanently blocked ever issuing that tenant
another one — `IssueLicenseUseCase`'s INSERT raised a raw `IntegrityError`
no `super_admin` could recover from through any UI or API this feature
ships. `test_license_repositories.py` proves the repository layer's RLS/
`SECURITY DEFINER` behavior in isolation; this file proves the *use cases'*
business rules hold across a full revoke-then-reissue cycle, which no
existing test exercised.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text

from lpg.application.common.errors import LicenseActivationFailedError, LicenseAlreadyIssuedError
from lpg.application.common.tenant import RequestTenantContext
from lpg.application.license.activate_license import ActivateLicenseCommand, ActivateLicenseUseCase
from lpg.application.license.issue_license import (
    IssueLicenseCommand,
    IssueLicenseUseCase,
    RevokeLicenseCommand,
    RevokeLicenseUseCase,
)
from lpg.domain.license.license import LicenseLifecycleState
from lpg.infrastructure.identity.token_hasher import Sha256TokenHasher
from lpg.infrastructure.persistence.database import Database
from lpg.infrastructure.persistence.repositories.license import SqlAlchemyLicenseRepository
from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from sqlalchemy.ext.asyncio import AsyncEngine

    from lpg.config.settings import Settings

pytestmark = pytest.mark.integration


class _NoopLicenseStatusChecker:
    """`ActivateLicenseUseCase`/`RevokeLicenseUseCase` both invalidate the
    Redis-backed status cache on every mutation — this suite's own concern
    is the use cases' business rules against real storage, not that cache
    (covered elsewhere), so `invalidate` is a no-op and `get_status` is
    never called by either use case."""

    async def get_status(self, tenant_id: uuid.UUID) -> LicenseLifecycleState:
        del tenant_id
        return LicenseLifecycleState.ACTIVE

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


async def _seed_tenant(admin_engine: AsyncEngine) -> uuid.UUID:
    async with admin_engine.begin() as conn:
        tenant_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.tenant (id, name, slug, primary_contact_email) "
                    "VALUES (gen_random_uuid(), 'License Lifecycle Test Co', :slug, "
                    "'ops@example.com') RETURNING id"
                ),
                {"slug": f"license-lifecycle-{uuid.uuid4().hex[:10]}"},
            )
        ).scalar_one()
        # `tests/integration/conftest.py`'s `_auto_activate_licenses_for_new_tenants`
        # trigger just gave this tenant a license — this suite intentionally
        # drives license issuance itself (that's the whole point of testing
        # `IssueLicenseUseCase` directly), so it needs a clean slate. Same
        # cleanup `test_license_repositories.py::_seed_tenant` does.
        await conn.execute(
            text("DELETE FROM platform.license WHERE tenant_id = :tenant_id"),
            {"tenant_id": str(tenant_id)},
        )
    return uuid.UUID(str(tenant_id))


class TestLicenseReissuanceAfterRevoke:
    async def test_issue_activate_revoke_reissue_reactivate_full_lifecycle(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        tenant_id = await _seed_tenant(admin_engine)
        context = RequestTenantContext(tenant_id=tenant_id)
        token_hasher = Sha256TokenHasher()
        status_checker = _NoopLicenseStatusChecker()

        async def _uow() -> AsyncIterator[SqlAlchemyUnitOfWork]:
            async for session in database.open_session(tenant_id=tenant_id):
                async with SqlAlchemyUnitOfWork(session, context) as uow:
                    yield uow

        # 1. Issue the first license.
        async for uow in _uow():
            repository = SqlAlchemyLicenseRepository(uow)
            first_license, first_key = await IssueLicenseUseCase(
                repository, token_hasher, uow
            ).execute(IssueLicenseCommand(tenant_id=tenant_id, plan_tier="standard"))
        first_license_id = first_license.id
        assert first_license.revoked_at is None

        # 2. Activate it.
        async for uow in _uow():
            repository = SqlAlchemyLicenseRepository(uow)
            activated = await ActivateLicenseUseCase(
                repository, token_hasher, status_checker, uow
            ).execute(ActivateLicenseCommand(tenant_id=tenant_id, presented_key=first_key))
        assert activated.id == first_license_id
        assert activated.activated_at is not None
        assert activated.compute_status(at=datetime.now(UTC)) is LicenseLifecycleState.ACTIVE

        # 3. Revoke it.
        async for uow in _uow():
            repository = SqlAlchemyLicenseRepository(uow)
            await RevokeLicenseUseCase(repository, status_checker, uow).execute(
                RevokeLicenseCommand(tenant_id=tenant_id)
            )

        # Issuing again *while* a non-revoked license exists is rejected —
        # the flip side of this fix: the partial unique index's guard rail
        # must still surface as a clean domain error, not a raw
        # IntegrityError, for a tenant that already has an active license.
        # (Re-seed a second tenant to prove this, since this tenant's only
        # license is now revoked and *should* be reissuable.)
        other_tenant_id = await _seed_tenant(admin_engine)
        other_context = RequestTenantContext(tenant_id=other_tenant_id)
        async for session in database.open_session(tenant_id=other_tenant_id):
            async with SqlAlchemyUnitOfWork(session, other_context) as uow:
                repository = SqlAlchemyLicenseRepository(uow)
                await IssueLicenseUseCase(repository, token_hasher, uow).execute(
                    IssueLicenseCommand(tenant_id=other_tenant_id, plan_tier="basic")
                )
        async for session in database.open_session(tenant_id=other_tenant_id):
            async with SqlAlchemyUnitOfWork(session, other_context) as uow:
                repository = SqlAlchemyLicenseRepository(uow)
                with pytest.raises(LicenseAlreadyIssuedError):
                    await IssueLicenseUseCase(repository, token_hasher, uow).execute(
                        IssueLicenseCommand(tenant_id=other_tenant_id, plan_tier="basic")
                    )

        # 4. Reissue for our original (now fully revoked) tenant — this is
        # the exact operation `f5746de5730e` exists to unblock. Must not
        # raise IntegrityError.
        async for uow in _uow():
            repository = SqlAlchemyLicenseRepository(uow)
            second_license, second_key = await IssueLicenseUseCase(
                repository, token_hasher, uow
            ).execute(IssueLicenseCommand(tenant_id=tenant_id, plan_tier="premium"))
        assert second_license.id != first_license_id
        assert second_license.revoked_at is None
        assert second_license.plan_tier == "premium"

        # 5. Reactivate — the *new* license, not the old revoked one.
        async for uow in _uow():
            repository = SqlAlchemyLicenseRepository(uow)
            reactivated = await ActivateLicenseUseCase(
                repository, token_hasher, status_checker, uow
            ).execute(ActivateLicenseCommand(tenant_id=tenant_id, presented_key=second_key))
        assert reactivated.id == second_license.id
        assert reactivated.compute_status(at=datetime.now(UTC)) is LicenseLifecycleState.ACTIVE

        # The old revoked key must never activate the new license — proves
        # `get_by_tenant_id` resolved to the new row, not the old one, and
        # that revoked history is immutable, not silently reused.
        async for uow in _uow():
            repository = SqlAlchemyLicenseRepository(uow)
            with pytest.raises(LicenseActivationFailedError):
                await ActivateLicenseUseCase(
                    repository, token_hasher, status_checker, uow
                ).execute(ActivateLicenseCommand(tenant_id=tenant_id, presented_key=first_key))

        # 6. Full history is preserved for audit purposes — both rows still
        # exist, not superseded/soft-deleted, per this fix's whole premise.
        async with admin_engine.begin() as conn:
            rows = (
                await conn.execute(
                    text(
                        "SELECT id, revoked_at, plan_tier FROM platform.license "
                        "WHERE tenant_id = :tenant_id ORDER BY issued_at"
                    ),
                    {"tenant_id": str(tenant_id)},
                )
            ).fetchall()
        assert len(rows) == 2
        assert rows[0].id == first_license_id
        assert rows[0].revoked_at is not None
        assert rows[0].plan_tier == "standard"
        assert rows[1].id == second_license.id
        assert rows[1].revoked_at is None
        assert rows[1].plan_tier == "premium"
