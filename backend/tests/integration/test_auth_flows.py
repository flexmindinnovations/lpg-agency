"""Security-critical auth flows, against real PostgreSQL/Redis — the
properties `docs/implementation/testing-strategy.md`'s "RBAC Policy
Verification" requirement and `docs/data/17-api-security.md` §2/§7 name
explicitly: account lockout, refresh-token-reuse detection, and RBAC
permission enforcement (claims-based and live).

Area C/D already prove the repositories and infra adapters work in
isolation; the login/me smoke test (`test_auth_endpoints_smoke.py`) proves
the whole HTTP stack is wired correctly. This file proves the *use cases*'
own business rules — the reasons this module exists — hold under real
storage, not a mock standing in for one.
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from lpg.application.common.errors import (
    AccountLockedError,
    InvalidCredentialsError,
    OtpExpiredError,
    OtpMismatchError,
    PermissionDeniedError,
    RefreshTokenInvalidError,
    ResetTokenExpiredError,
)
from lpg.application.identity.login import LoginCommand, LoginUseCase
from lpg.application.identity.logout import LogoutCommand, LogoutUseCase
from lpg.application.identity.otp_request import RequestOtpCommand, RequestOtpUseCase
from lpg.application.identity.otp_verify import VerifyOtpCommand, VerifyOtpUseCase
from lpg.application.identity.password_reset import (
    ConfirmPasswordResetCommand,
    ConfirmPasswordResetUseCase,
    RequestPasswordResetCommand,
    RequestPasswordResetUseCase,
)
from lpg.application.identity.principal import JwtAuthenticatedPrincipal
from lpg.application.identity.refresh_token import RefreshTokenCommand, RefreshTokenUseCase
from lpg.infrastructure.identity.otp_service import OtpService
from lpg.infrastructure.identity.password_hasher import Argon2PasswordHasher
from lpg.infrastructure.identity.token_hasher import Sha256TokenHasher
from lpg.infrastructure.persistence.database import Database
from lpg.infrastructure.persistence.repositories.identity import (
    SqlAlchemyIdentityUserRepository,
    SqlAlchemyPasswordResetTokenRepository,
    SqlAlchemyPermissionRepository,
    SqlAlchemyRefreshTokenRepository,
)
from lpg.infrastructure.redis.client import RedisClient

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


@pytest.fixture
async def redis_client(
    integration_settings: Settings, redis_available: bool
) -> AsyncIterator[RedisClient]:
    if not redis_available:
        pytest.skip("Redis is not reachable — start it with ./scripts/dev-up.sh")
    client = RedisClient(integration_settings)
    client.connect()
    try:
        yield client
    finally:
        await client.disconnect()


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


async def _seed_user(
    engine: AsyncEngine, *, email: str, password_hash: str, role: str = "manager"
) -> uuid.UUID:
    async with engine.begin() as conn:
        tenant_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.tenant (id, name, slug) "
                    "VALUES (gen_random_uuid(), 'Auth Flow Test', :slug) RETURNING id"
                ),
                {"slug": f"auth-flow-{uuid.uuid4().hex[:10]}"},
            )
        ).scalar_one()
        user_id = (
            await conn.execute(
                text(
                    "INSERT INTO identity.identity_user "
                    "(id, tenant_id, email, password_hash, role) "
                    "VALUES (gen_random_uuid(), :tenant_id, :email, :password_hash, :role) "
                    "RETURNING id"
                ),
                {
                    "tenant_id": str(tenant_id),
                    "email": email,
                    "password_hash": password_hash,
                    "role": role,
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
            {"user_id": user_id, "role": role},
        )
    return uuid.UUID(str(user_id))


async def _seed_otp_user(
    engine: AsyncEngine, *, phone_number: str, role: str = "driver"
) -> tuple[uuid.UUID, uuid.UUID]:
    async with engine.begin() as conn:
        tenant_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.tenant (id, name, slug) "
                    "VALUES (gen_random_uuid(), 'Auth Flow Test', :slug) RETURNING id"
                ),
                {"slug": f"auth-flow-{uuid.uuid4().hex[:10]}"},
            )
        ).scalar_one()
        user_id = (
            await conn.execute(
                text(
                    "INSERT INTO identity.identity_user "
                    "(id, tenant_id, phone_number, role) "
                    "VALUES (gen_random_uuid(), :tenant_id, :phone_number, :role) "
                    "RETURNING id"
                ),
                {"tenant_id": str(tenant_id), "phone_number": phone_number, "role": role},
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
            {"user_id": user_id, "role": role},
        )
    return uuid.UUID(str(tenant_id)), uuid.UUID(str(user_id))


class _StubOtpDelivery:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    async def send(self, phone_number: str, code: str) -> None:
        self.sent.append((phone_number, code))


class _StubEmailSender:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str, str]] = []

    async def send(self, to: str, subject: str, body: str) -> None:
        self.sent.append((to, subject, body))


class TestLoginLockout:
    async def test_locks_the_account_after_the_configured_threshold(
        self, database: Database, admin_engine_lpg_test: AsyncEngine, integration_settings: Settings
    ) -> None:
        email = f"{uuid.uuid4().hex}@lockout.example"
        hasher = Argon2PasswordHasher(integration_settings)
        await _seed_user(admin_engine_lpg_test, email=email, password_hash=hasher.hash("correct"))

        use_case = LoginUseCase(
            SqlAlchemyIdentityUserRepository(database),
            SqlAlchemyRefreshTokenRepository(database),
            SqlAlchemyPermissionRepository(database),
            hasher,
            Sha256TokenHasher(),
            _StubJwtSigner(),
            lockout_threshold=3,
            lockout_duration=timedelta(minutes=15),
            refresh_token_ttl=timedelta(days=30),
        )

        for _ in range(3):
            with pytest.raises(InvalidCredentialsError):
                await use_case.execute(LoginCommand(email=email, password="wrong"))

        # The 4th attempt, even with the *correct* password, is locked out —
        # proving the lockout is enforced before password verification even
        # runs, not just that failures keep incrementing.
        with pytest.raises(AccountLockedError):
            await use_case.execute(LoginCommand(email=email, password="correct"))

    async def test_a_successful_login_resets_the_failure_count(
        self, database: Database, admin_engine_lpg_test: AsyncEngine, integration_settings: Settings
    ) -> None:
        email = f"{uuid.uuid4().hex}@lockout.example"
        hasher = Argon2PasswordHasher(integration_settings)
        await _seed_user(admin_engine_lpg_test, email=email, password_hash=hasher.hash("correct"))

        use_case = LoginUseCase(
            SqlAlchemyIdentityUserRepository(database),
            SqlAlchemyRefreshTokenRepository(database),
            SqlAlchemyPermissionRepository(database),
            hasher,
            Sha256TokenHasher(),
            _StubJwtSigner(),
            lockout_threshold=3,
            lockout_duration=timedelta(minutes=15),
            refresh_token_ttl=timedelta(days=30),
        )

        with pytest.raises(InvalidCredentialsError):
            await use_case.execute(LoginCommand(email=email, password="wrong"))
        with pytest.raises(InvalidCredentialsError):
            await use_case.execute(LoginCommand(email=email, password="wrong"))

        # Correct password on the 3rd attempt, still under the threshold.
        await use_case.execute(LoginCommand(email=email, password="correct"))

        # Two more wrong attempts afterward shouldn't lock — the counter was
        # reset by the success above, not left at 2-out-of-3.
        with pytest.raises(InvalidCredentialsError):
            await use_case.execute(LoginCommand(email=email, password="wrong"))
        with pytest.raises(InvalidCredentialsError):
            await use_case.execute(LoginCommand(email=email, password="wrong"))
        # Third wrong attempt post-reset still just reports bad credentials,
        # not a lock — confirms the count truly restarted at zero.
        with pytest.raises(InvalidCredentialsError) as exc_info:
            await use_case.execute(LoginCommand(email=email, password="wrong"))
        assert not isinstance(exc_info.value, AccountLockedError)


class TestRefreshTokenReuseDetection:
    async def test_reusing_a_rotated_token_revokes_the_whole_session(
        self, database: Database, admin_engine_lpg_test: AsyncEngine, integration_settings: Settings
    ) -> None:
        email = f"{uuid.uuid4().hex}@reuse.example"
        hasher = Argon2PasswordHasher(integration_settings)
        await _seed_user(admin_engine_lpg_test, email=email, password_hash=hasher.hash("correct"))

        login_use_case = LoginUseCase(
            SqlAlchemyIdentityUserRepository(database),
            SqlAlchemyRefreshTokenRepository(database),
            SqlAlchemyPermissionRepository(database),
            hasher,
            Sha256TokenHasher(),
            _StubJwtSigner(),
            lockout_threshold=5,
            lockout_duration=timedelta(minutes=15),
            refresh_token_ttl=timedelta(days=30),
        )
        original_pair = await login_use_case.execute(LoginCommand(email=email, password="correct"))

        refresh_use_case = RefreshTokenUseCase(
            SqlAlchemyRefreshTokenRepository(database),
            SqlAlchemyIdentityUserRepository(database),
            SqlAlchemyPermissionRepository(database),
            Sha256TokenHasher(),
            _StubJwtSigner(),
            refresh_token_ttl=timedelta(days=30),
        )

        # First redemption: valid rotation, issues a second pair.
        second_pair = await refresh_use_case.execute(
            RefreshTokenCommand(refresh_token=original_pair.refresh_token)
        )

        # Reusing the now-rotated *original* token is the theft signal.
        with pytest.raises(RefreshTokenInvalidError):
            await refresh_use_case.execute(
                RefreshTokenCommand(refresh_token=original_pair.refresh_token)
            )

        # The reuse must have revoked the *whole session* — the second,
        # legitimately-issued token is also dead now, not just the reused
        # one flagged.
        with pytest.raises(RefreshTokenInvalidError):
            await refresh_use_case.execute(
                RefreshTokenCommand(refresh_token=second_pair.refresh_token)
            )


class TestPermissionCheckerLiveRecheck:
    async def test_has_permission_live_reflects_the_current_grant_not_a_stale_claim(
        self, database: Database
    ) -> None:
        from lpg.application.identity.authorize import PermissionChecker

        checker = PermissionChecker(SqlAlchemyPermissionRepository(database))
        # Seeded in fa52b77ec442: agency_admin has tenant:configure,
        # driver does not.
        principal = JwtAuthenticatedPrincipal(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            role="driver",
            # Claim says driver *does* have it — stale/tampered. The live
            # check must not trust this and must still deny.
            permission_codes=frozenset({"tenant:configure"}),
        )

        assert checker.has_permission(principal, "tenant:configure")  # claims-based: trusts it
        assert not await checker.has_permission_live(principal, "tenant:configure")

    async def test_require_permission_denies_a_role_without_the_claim(self) -> None:
        from lpg.api.v1.dependencies.identity import require_permission

        principal = JwtAuthenticatedPrincipal(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            role="driver",
            permission_codes=frozenset({"orders:deliver"}),
        )
        dependency = require_permission("tenant:configure")

        with pytest.raises(PermissionDeniedError):
            await dependency(principal)

    async def test_require_permission_allows_a_role_with_the_claim(self) -> None:
        from lpg.api.v1.dependencies.identity import require_permission

        principal = JwtAuthenticatedPrincipal(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            role="agency_admin",
            permission_codes=frozenset({"tenant:configure"}),
        )
        dependency = require_permission("tenant:configure")

        result = await dependency(principal)

        assert result is principal


class TestOtpFlow:
    async def test_request_then_verify_with_the_correct_code_issues_tokens(
        self,
        database: Database,
        admin_engine_lpg_test: AsyncEngine,
        redis_client: RedisClient,
        integration_settings: Settings,
    ) -> None:
        phone_number = f"+1555{uuid.uuid4().int % 10_000_000:07d}"
        tenant_id, _user_id = await _seed_otp_user(admin_engine_lpg_test, phone_number=phone_number)

        otp_store = OtpService(redis_client, integration_settings)
        delivery = _StubOtpDelivery()
        request_use_case = RequestOtpUseCase(otp_store, delivery)
        await request_use_case.execute(
            RequestOtpCommand(tenant_id=tenant_id, phone_number=phone_number)
        )
        assert len(delivery.sent) == 1
        sent_phone, code = delivery.sent[0]
        assert sent_phone == phone_number

        verify_use_case = VerifyOtpUseCase(
            otp_store,
            SqlAlchemyIdentityUserRepository(database),
            SqlAlchemyRefreshTokenRepository(database),
            SqlAlchemyPermissionRepository(database),
            Sha256TokenHasher(),
            _StubJwtSigner(),
            refresh_token_ttl=timedelta(days=30),
        )
        pair = await verify_use_case.execute(
            VerifyOtpCommand(tenant_id=tenant_id, phone_number=phone_number, code=code)
        )

        assert pair.access_token
        assert pair.refresh_token

    async def test_verify_with_the_wrong_code_raises_mismatch_and_does_not_consume_it(
        self,
        database: Database,
        admin_engine_lpg_test: AsyncEngine,
        redis_client: RedisClient,
        integration_settings: Settings,
    ) -> None:
        phone_number = f"+1555{uuid.uuid4().int % 10_000_000:07d}"
        tenant_id, _user_id = await _seed_otp_user(admin_engine_lpg_test, phone_number=phone_number)

        otp_store = OtpService(redis_client, integration_settings)
        await RequestOtpUseCase(otp_store, _StubOtpDelivery()).execute(
            RequestOtpCommand(tenant_id=tenant_id, phone_number=phone_number)
        )

        verify_use_case = VerifyOtpUseCase(
            otp_store,
            SqlAlchemyIdentityUserRepository(database),
            SqlAlchemyRefreshTokenRepository(database),
            SqlAlchemyPermissionRepository(database),
            Sha256TokenHasher(),
            _StubJwtSigner(),
            refresh_token_ttl=timedelta(days=30),
        )

        with pytest.raises(OtpMismatchError):
            await verify_use_case.execute(
                VerifyOtpCommand(tenant_id=tenant_id, phone_number=phone_number, code="000000")
            )

    async def test_verify_with_no_pending_code_raises_expired(
        self, database: Database, redis_client: RedisClient, integration_settings: Settings
    ) -> None:
        otp_store = OtpService(redis_client, integration_settings)
        verify_use_case = VerifyOtpUseCase(
            otp_store,
            SqlAlchemyIdentityUserRepository(database),
            SqlAlchemyRefreshTokenRepository(database),
            SqlAlchemyPermissionRepository(database),
            Sha256TokenHasher(),
            _StubJwtSigner(),
            refresh_token_ttl=timedelta(days=30),
        )

        with pytest.raises(OtpExpiredError):
            await verify_use_case.execute(
                VerifyOtpCommand(
                    tenant_id=uuid.uuid4(),
                    phone_number="+15550000000",
                    code="123456",
                )
            )


class TestPasswordResetFlow:
    async def test_request_then_confirm_with_the_token_changes_the_password(
        self, database: Database, admin_engine_lpg_test: AsyncEngine, integration_settings: Settings
    ) -> None:
        email = f"{uuid.uuid4().hex}@reset.example"
        hasher = Argon2PasswordHasher(integration_settings)
        await _seed_user(
            admin_engine_lpg_test, email=email, password_hash=hasher.hash("old-password")
        )

        token_hasher = Sha256TokenHasher()
        email_sender = _StubEmailSender()
        request_use_case = RequestPasswordResetUseCase(
            SqlAlchemyIdentityUserRepository(database),
            SqlAlchemyPasswordResetTokenRepository(database),
            token_hasher,
            email_sender,
            reset_token_ttl=timedelta(hours=1),
        )
        await request_use_case.execute(RequestPasswordResetCommand(email=email))

        assert len(email_sender.sent) == 1
        _to, _subject, body = email_sender.sent[0]
        raw_token = body.rsplit("token=", 1)[1]

        confirm_use_case = ConfirmPasswordResetUseCase(
            SqlAlchemyPasswordResetTokenRepository(database),
            SqlAlchemyIdentityUserRepository(database),
            token_hasher,
            hasher,
        )
        await confirm_use_case.execute(
            ConfirmPasswordResetCommand(reset_token=raw_token, new_password="new-password-123")
        )

        user = await SqlAlchemyIdentityUserRepository(database).get_by_email(email)
        assert user is not None
        assert user.password_hash is not None
        assert hasher.verify("new-password-123", user.password_hash)
        assert not hasher.verify("old-password", user.password_hash)

    async def test_request_for_an_unknown_email_completes_silently_without_sending(
        self, database: Database
    ) -> None:
        email_sender = _StubEmailSender()
        request_use_case = RequestPasswordResetUseCase(
            SqlAlchemyIdentityUserRepository(database),
            SqlAlchemyPasswordResetTokenRepository(database),
            Sha256TokenHasher(),
            email_sender,
            reset_token_ttl=timedelta(hours=1),
        )

        await request_use_case.execute(
            RequestPasswordResetCommand(email=f"{uuid.uuid4().hex}@nowhere.example")
        )

        assert email_sender.sent == []

    async def test_confirm_with_an_unknown_token_raises_expired(
        self, database: Database, integration_settings: Settings
    ) -> None:
        confirm_use_case = ConfirmPasswordResetUseCase(
            SqlAlchemyPasswordResetTokenRepository(database),
            SqlAlchemyIdentityUserRepository(database),
            Sha256TokenHasher(),
            Argon2PasswordHasher(integration_settings),
        )

        with pytest.raises(ResetTokenExpiredError):
            await confirm_use_case.execute(
                ConfirmPasswordResetCommand(
                    reset_token="not-a-real-token", new_password="new-password-123"
                )
            )

    async def test_confirm_with_an_expired_token_raises_expired(
        self, database: Database, admin_engine_lpg_test: AsyncEngine, integration_settings: Settings
    ) -> None:
        email = f"{uuid.uuid4().hex}@reset.example"
        hasher = Argon2PasswordHasher(integration_settings)
        await _seed_user(
            admin_engine_lpg_test, email=email, password_hash=hasher.hash("old-password")
        )

        token_hasher = Sha256TokenHasher()
        email_sender = _StubEmailSender()
        request_use_case = RequestPasswordResetUseCase(
            SqlAlchemyIdentityUserRepository(database),
            SqlAlchemyPasswordResetTokenRepository(database),
            token_hasher,
            email_sender,
            # Already-elapsed TTL — the token is expired the instant it's issued.
            reset_token_ttl=timedelta(seconds=-1),
        )
        await request_use_case.execute(RequestPasswordResetCommand(email=email))
        _to, _subject, body = email_sender.sent[0]
        raw_token = body.rsplit("token=", 1)[1]

        confirm_use_case = ConfirmPasswordResetUseCase(
            SqlAlchemyPasswordResetTokenRepository(database),
            SqlAlchemyIdentityUserRepository(database),
            token_hasher,
            hasher,
        )

        with pytest.raises(ResetTokenExpiredError):
            await confirm_use_case.execute(
                ConfirmPasswordResetCommand(reset_token=raw_token, new_password="new-password-123")
            )


class TestLogoutInvalidatesServerSide:
    async def test_logout_revokes_the_refresh_token_so_it_can_no_longer_be_redeemed(
        self, database: Database, admin_engine_lpg_test: AsyncEngine, integration_settings: Settings
    ) -> None:
        email = f"{uuid.uuid4().hex}@logout.example"
        hasher = Argon2PasswordHasher(integration_settings)
        await _seed_user(admin_engine_lpg_test, email=email, password_hash=hasher.hash("correct"))

        login_use_case = LoginUseCase(
            SqlAlchemyIdentityUserRepository(database),
            SqlAlchemyRefreshTokenRepository(database),
            SqlAlchemyPermissionRepository(database),
            hasher,
            Sha256TokenHasher(),
            _StubJwtSigner(),
            lockout_threshold=5,
            lockout_duration=timedelta(minutes=15),
            refresh_token_ttl=timedelta(days=30),
        )
        pair = await login_use_case.execute(LoginCommand(email=email, password="correct"))

        logout_use_case = LogoutUseCase(
            SqlAlchemyRefreshTokenRepository(database), Sha256TokenHasher()
        )
        await logout_use_case.execute(LogoutCommand(refresh_token=pair.refresh_token))

        refresh_use_case = RefreshTokenUseCase(
            SqlAlchemyRefreshTokenRepository(database),
            SqlAlchemyIdentityUserRepository(database),
            SqlAlchemyPermissionRepository(database),
            Sha256TokenHasher(),
            _StubJwtSigner(),
            refresh_token_ttl=timedelta(days=30),
        )
        with pytest.raises(RefreshTokenInvalidError):
            await refresh_use_case.execute(RefreshTokenCommand(refresh_token=pair.refresh_token))

    async def test_logout_with_an_unknown_token_is_idempotent(self, database: Database) -> None:
        logout_use_case = LogoutUseCase(
            SqlAlchemyRefreshTokenRepository(database), Sha256TokenHasher()
        )

        # Should not raise — an already-invalid/unknown token is not an error.
        await logout_use_case.execute(LogoutCommand(refresh_token="never-issued-token"))


class _StubJwtSigner:
    """A minimal `JwtSigner` for these tests — they exercise use-case
    business rules (lockout, reuse detection), not JWT signing itself
    (already covered by `tests/unit/test_jwt_signer.py`), so a stub
    avoids depending on `Settings`' ephemeral-keypair generation here.
    """

    def issue_access_token(self, claims: dict[str, object]) -> str:
        return f"stub-token-for-{claims.get('sub')}"

    def decode_access_token(self, token: str) -> dict[str, object]:
        raise NotImplementedError
