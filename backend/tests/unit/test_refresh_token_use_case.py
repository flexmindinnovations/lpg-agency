"""`RefreshTokenUseCase` — rotation, theft detection and the grace window for a
lost response. In-memory fakes only: no database."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from lpg.application.common.errors import RefreshTokenInvalidError
from lpg.application.identity.refresh_token import RefreshTokenCommand, RefreshTokenUseCase
from lpg.domain.identity.refresh_token import RefreshToken
from lpg.domain.identity.user import IdentityUser
from lpg.domain.license.license import LicenseLifecycleState

_GRACE = timedelta(seconds=120)


class _Tokens:
    """Refresh tokens by hash, and the session-wide revocation."""

    def __init__(self) -> None:
        self.by_hash: dict[str, RefreshToken] = {}
        self.revoked_users: list[uuid.UUID] = []

    async def get_by_token_hash(self, token_hash: str) -> RefreshToken | None:
        return self.by_hash.get(token_hash)

    async def save(self, token: RefreshToken) -> None:
        self.by_hash[token.token_hash] = token

    async def revoke_all_for_user(self, user_id: uuid.UUID) -> None:
        self.revoked_users.append(user_id)
        for token in self.by_hash.values():
            if token.user_id == user_id:
                token.revoke()


class _Users:
    def __init__(self, user: IdentityUser) -> None:
        self._user = user

    async def get(self, user_id: uuid.UUID) -> IdentityUser | None:
        return self._user if user_id == self._user.id else None


class _Permissions:
    async def get_permission_codes_for_user(self, user_id: uuid.UUID) -> frozenset[str]:
        del user_id
        return frozenset()


class _Hasher:
    def hash(self, raw: str) -> str:
        return f"h:{raw}"


class _Signer:
    def issue_access_token(self, claims: dict[str, object]) -> str:
        return f"access-for-{claims['sub']}"


class _ActiveLicense:
    async def get_status(self, tenant_id: uuid.UUID) -> LicenseLifecycleState:
        del tenant_id
        return LicenseLifecycleState.ACTIVE


class _ActiveTenant:
    async def get_status(self, tenant_id: uuid.UUID) -> str:
        del tenant_id
        return "active"


def _user() -> IdentityUser:
    return IdentityUser(
        uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        branch_id=None,
        email="owner@example.com",
        phone_number=None,
        password_hash="argon2-hash",
        role="agency_admin",
    )


def _stored_token(user: IdentityUser, tokens: _Tokens, *, raw: str = "raw-1") -> RefreshToken:
    now = datetime.now(UTC)
    token = RefreshToken(
        uuid.uuid4(),
        user_id=user.id,
        token_hash=_Hasher().hash(raw),
        issued_at=now,
        expires_at=now + timedelta(days=30),
    )
    tokens.by_hash[token.token_hash] = token
    return token


def _use_case(user: IdentityUser, tokens: _Tokens, *, grace: timedelta) -> RefreshTokenUseCase:
    return RefreshTokenUseCase(
        tokens,  # type: ignore[arg-type]
        _Users(user),  # type: ignore[arg-type]
        _Permissions(),  # type: ignore[arg-type]
        _Hasher(),  # type: ignore[arg-type]
        _Signer(),  # type: ignore[arg-type]
        _ActiveLicense(),  # type: ignore[arg-type]
        _ActiveTenant(),  # type: ignore[arg-type]
        refresh_token_ttl=timedelta(days=30),
        reuse_grace=grace,
    )


class TestRefreshTokenUseCase:
    async def test_rotates_and_marks_the_old_token(self) -> None:
        user, tokens = _user(), _Tokens()
        old = _stored_token(user, tokens)

        pair = await _use_case(user, tokens, grace=_GRACE).execute(
            RefreshTokenCommand(refresh_token="raw-1")
        )

        assert old.rotated_at is not None
        assert old.replaced_by_id == pair.refresh_token_id

    async def test_a_retry_inside_the_grace_window_gets_a_fresh_pair(self) -> None:
        user, tokens = _user(), _Tokens()
        old = _stored_token(user, tokens)
        use_case = _use_case(user, tokens, grace=_GRACE)
        first = await use_case.execute(RefreshTokenCommand(refresh_token="raw-1"))
        first_rotated_at = old.rotated_at

        # The phone never got `first` and presents the same token again.
        retry = await use_case.execute(RefreshTokenCommand(refresh_token="raw-1"))

        assert retry.refresh_token != first.refresh_token
        assert tokens.revoked_users == []  # not treated as theft
        assert old.rotated_at == first_rotated_at  # stays the first rotation
        # Either pair keeps working.
        await use_case.execute(RefreshTokenCommand(refresh_token=retry.refresh_token))

    async def test_reuse_after_the_window_is_theft_and_ends_every_session(self) -> None:
        user, tokens = _user(), _Tokens()
        old = _stored_token(user, tokens)
        use_case = _use_case(user, tokens, grace=_GRACE)
        await use_case.execute(RefreshTokenCommand(refresh_token="raw-1"))
        # Pretend the rotation happened ten minutes ago.
        old._rotated_at = datetime.now(UTC) - timedelta(minutes=10)

        with pytest.raises(RefreshTokenInvalidError):
            await use_case.execute(RefreshTokenCommand(refresh_token="raw-1"))

        assert tokens.revoked_users == [user.id]

    async def test_with_no_grace_any_reuse_is_theft(self) -> None:
        user, tokens = _user(), _Tokens()
        _stored_token(user, tokens)
        use_case = _use_case(user, tokens, grace=timedelta(0))
        await use_case.execute(RefreshTokenCommand(refresh_token="raw-1"))

        with pytest.raises(RefreshTokenInvalidError):
            await use_case.execute(RefreshTokenCommand(refresh_token="raw-1"))

        assert tokens.revoked_users == [user.id]

    async def test_a_revoked_session_gets_no_grace(self) -> None:
        user, tokens = _user(), _Tokens()
        old = _stored_token(user, tokens)
        use_case = _use_case(user, tokens, grace=_GRACE)
        await use_case.execute(RefreshTokenCommand(refresh_token="raw-1"))
        old.revoke()

        with pytest.raises(RefreshTokenInvalidError):
            await use_case.execute(RefreshTokenCommand(refresh_token="raw-1"))
