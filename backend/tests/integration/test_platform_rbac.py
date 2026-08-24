"""RBAC and authentication coverage for the `/platform/*` dependency chain
(`api/v1/dependencies/platform.py`) — mirrors `test_admin_license_rbac.py`'s
shape exactly, one level removed from tenant context.

The `JwtPlatformPrincipalResolver` coverage here is the actual proof this
whole plan exists for: a JWT with no `tenant_id` claim (a genuine
`super_admin` session) is accepted, and one *with* a real `tenant_id` claim
(any tenant-scoped role, even one holding the right permission code) is
rejected outright, before any permission check even runs — the exact
boundary `JwtTenantResolver.resolve()`'s own "not supported yet" message
describes from the other side.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from starlette.requests import Request

from lpg.api.v1.dependencies.platform import (
    require_live_platform_permission,
    require_platform_permission,
)
from lpg.application.common.errors import PermissionDeniedError, TenantContextMissingError
from lpg.application.platform.principal import JwtPlatformPrincipal
from lpg.config.settings import Settings
from lpg.infrastructure.identity.jwt_platform_principal_resolver import (
    JwtPlatformPrincipalResolver,
)
from lpg.infrastructure.identity.jwt_signer import PyJwtSigner
from lpg.infrastructure.persistence.database import Database

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from sqlalchemy.ext.asyncio import AsyncEngine

pytestmark = pytest.mark.integration


@pytest.fixture
async def database(
    integration_settings: Settings, postgres_available: bool
) -> AsyncIterator[Database]:
    """Also registers into `AppState` — unlike `test_admin_license_rbac.py`'s
    identically-named fixture (which hands its `Database` straight to a
    locally-constructed `PermissionChecker`, bypassing `AppState` entirely),
    `require_live_platform_permission` calls `get_permission_repository()`
    internally rather than taking one as an explicit parameter, so it can
    only ever resolve a database through `AppState` — same reasoning
    `test_tenant_dependency_chain.py`'s `app_database` fixture already
    documents for `AppState.jwt_signer`.
    """
    if not postgres_available:
        pytest.skip("PostgreSQL is not reachable — start it with ./scripts/dev-up.sh")
    from lpg.api.app import get_app_state

    db = Database(integration_settings)
    db.connect()
    state = get_app_state()
    state.database = db
    try:
        yield db
    finally:
        state.database = None
        await db.disconnect()


@pytest.fixture
async def admin_engine_lpg_test(postgres_available: bool) -> AsyncIterator[AsyncEngine]:
    if not postgres_available:
        pytest.skip("PostgreSQL is not reachable — start it with ./scripts/dev-up.sh")
    engine = create_async_engine(
        "postgresql+asyncpg://lpg_admin:dev_only_not_a_real_secret@localhost:55432/lpg_test"
    )
    try:
        yield engine
    finally:
        await engine.dispose()


def _bearer_request(token: str) -> Request:
    encoded = [(b"authorization", f"Bearer {token}".encode())]
    return Request(scope={"type": "http", "headers": encoded})


class TestJwtPlatformPrincipalResolver:
    async def test_accepts_a_super_admin_token_with_no_tenant_claim(self) -> None:
        signer = PyJwtSigner(Settings(environment="local"))
        user_id = uuid.uuid4()
        token = signer.issue_access_token(
            {"sub": str(user_id), "role": "super_admin", "scope": "tenant:manage_platform"}
        )
        resolver = JwtPlatformPrincipalResolver(signer)

        principal = await resolver.resolve(_bearer_request(token))

        assert principal.user_id == user_id
        assert principal.role == "super_admin"
        assert "tenant:manage_platform" in principal.permission_codes

    async def test_rejects_a_tenant_scoped_role_even_with_the_right_permission_claim(
        self,
    ) -> None:
        """A JWT claiming `agency_admin` with `tenant:manage_platform` in its
        `scope` (tampered, or simply the wrong token type for this route)
        must never resolve — D-01 makes `super_admin` the only role a
        `PlatformPrincipal` can ever represent, checked before any
        permission code."""
        signer = PyJwtSigner(Settings(environment="local"))
        token = signer.issue_access_token(
            {
                "sub": str(uuid.uuid4()),
                "tenant_id": str(uuid.uuid4()),
                "role": "agency_admin",
                "scope": "tenant:manage_platform",
            }
        )
        resolver = JwtPlatformPrincipalResolver(signer)

        with pytest.raises(PermissionDeniedError):
            await resolver.resolve(_bearer_request(token))

    async def test_rejects_a_missing_bearer_token(self) -> None:
        signer = PyJwtSigner(Settings(environment="local"))
        resolver = JwtPlatformPrincipalResolver(signer)

        with pytest.raises(TenantContextMissingError):
            await resolver.resolve(Request(scope={"type": "http", "headers": []}))


class TestClaimsBasedChecks:
    async def test_denies_a_super_admin_without_tenant_manage_platform(self) -> None:
        principal = JwtPlatformPrincipal(
            user_id=uuid.uuid4(),
            role="super_admin",
            permission_codes=frozenset({"license:manage_platform"}),
        )
        dependency = require_platform_permission("tenant:manage_platform")

        with pytest.raises(PermissionDeniedError):
            await dependency(principal)

    async def test_allows_a_super_admin_with_tenant_manage_platform(self) -> None:
        principal = JwtPlatformPrincipal(
            user_id=uuid.uuid4(),
            role="super_admin",
            permission_codes=frozenset({"tenant:manage_platform"}),
        )
        dependency = require_platform_permission("tenant:manage_platform")

        result = await dependency(principal)

        assert result is principal


class TestLivePermissionCheckForTenantManagePlatform:
    """Seeded in `03dd1af6ff59`: only `super_admin` has
    `tenant:manage_platform`."""

    async def test_denies_a_tampered_claim_with_no_real_grant(
        self, database: Database  # noqa: ARG002 - side effect: populates app state
    ) -> None:
        principal = JwtPlatformPrincipal(
            user_id=uuid.uuid4(),
            role="super_admin",
            # Claim says this principal has it — no matching row was ever
            # inserted into identity_user_permission. The live check must
            # not trust the claim alone.
            permission_codes=frozenset({"tenant:manage_platform"}),
        )
        dependency = require_live_platform_permission("tenant:manage_platform")

        with pytest.raises(PermissionDeniedError):
            await dependency(principal)

    async def test_allows_a_real_super_admin(
        self, database: Database, admin_engine_lpg_test: AsyncEngine
    ) -> None:
        del database  # only needed to ensure Postgres is reachable
        user_id = uuid.uuid4()
        email = f"{uuid.uuid4().hex}@platform-rbac.example"

        async with admin_engine_lpg_test.begin() as session:
            await session.execute(
                text(
                    "INSERT INTO identity.identity_user "
                    "(id, tenant_id, email, password_hash, role) "
                    "VALUES (:user_id, NULL, :email, 'hash', 'super_admin')"
                ),
                {"user_id": user_id, "email": email},
            )
            await session.execute(
                text(
                    "INSERT INTO identity.identity_user_permission (user_id, permission_id) "
                    "SELECT :user_id, id FROM identity.permission "
                    "WHERE code = 'tenant:manage_platform'"
                ),
                {"user_id": user_id},
            )

        principal = JwtPlatformPrincipal(
            user_id=user_id,
            role="super_admin",
            permission_codes=frozenset({"tenant:manage_platform"}),
        )
        dependency = require_live_platform_permission("tenant:manage_platform")

        result = await dependency(principal)

        assert result is principal
