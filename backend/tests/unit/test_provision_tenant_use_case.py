"""`ProvisionTenantUseCase` — ordering and failure handling, no database.

The real `InviteStaffUserUseCase` is used (only its collaborators are faked),
because the point of the refactor was to reuse it, and its token behaviour is
part of what this use case returns.
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import TYPE_CHECKING

import pytest

from lpg.application.common.errors import ConflictError
from lpg.application.identity.staff_user import InviteStaffUserUseCase
from lpg.application.tenant.provision_tenant import (
    FIRST_ADMIN_ROLE,
    ProvisionTenantCommand,
    ProvisionTenantUseCase,
)
from lpg.domain.common.base import InvariantViolation
from lpg.domain.identity.user import IdentityUser

if TYPE_CHECKING:
    from lpg.domain.identity.password_reset_token import PasswordResetToken
    from lpg.domain.tenant.tenant import Tenant


class _Calls:
    def __init__(self) -> None:
        self.log: list[str] = []


class _FakeTenantRepository:
    def __init__(self, calls: _Calls) -> None:
        self._calls = calls
        self.added: list[Tenant] = []

    async def add(self, tenant: Tenant) -> None:
        self._calls.log.append("tenant.add")
        self.added.append(tenant)


class _FakeUnitOfWork:
    def __init__(self, calls: _Calls) -> None:
        self._calls = calls

    async def commit(self) -> None:
        self._calls.log.append("uow.commit")


class _FakeUserRepository:
    def __init__(self, existing_emails: set[str] | None = None) -> None:
        self._existing = existing_emails or set()

    async def get_by_email(self, email: str) -> IdentityUser | None:
        if email in self._existing:
            return IdentityUser(
                uuid.uuid4(),
                tenant_id=uuid.uuid4(),
                branch_id=None,
                email=email,
                phone_number=None,
                password_hash="x",
                role="manager",
            )
        return None


class _FakeStaffRepository:
    def __init__(self, calls: _Calls, *, fail: bool = False) -> None:
        self._calls = calls
        self._fail = fail
        self.added: list[IdentityUser] = []

    async def add(self, user: IdentityUser) -> None:
        self._calls.log.append("staff.add")
        if self._fail:
            msg = "database went away"
            raise RuntimeError(msg)
        self.added.append(user)


class _FakeResetTokenRepository:
    def __init__(self) -> None:
        self.saved: list[PasswordResetToken] = []

    async def save(self, token: PasswordResetToken) -> None:
        self.saved.append(token)


class _FakeTokenHasher:
    def hash(self, raw: str) -> str:
        return f"hashed:{raw}"


class _FakeEmailSender:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    async def send(self, to: str, subject: str, body: str) -> None:
        del body
        self.sent.append((to, subject))


class _Harness:
    def __init__(
        self, *, existing_emails: set[str] | None = None, invite_fails: bool = False
    ) -> None:
        self.calls = _Calls()
        self.tenants = _FakeTenantRepository(self.calls)
        self.staff = _FakeStaffRepository(self.calls, fail=invite_fails)
        self.reset_tokens = _FakeResetTokenRepository()
        self.email = _FakeEmailSender()
        self.aborted: list[uuid.UUID] = []

        async def _abort(tenant_id: uuid.UUID) -> None:
            self.calls.log.append("abort")
            self.aborted.append(tenant_id)

        self.use_case = ProvisionTenantUseCase(
            self.tenants,  # type: ignore[arg-type]
            _FakeUnitOfWork(self.calls),  # type: ignore[arg-type]
            _FakeUserRepository(existing_emails),  # type: ignore[arg-type]
            lambda _tenant_id: InviteStaffUserUseCase(
                self.staff,  # type: ignore[arg-type]
                self.reset_tokens,  # type: ignore[arg-type]
                _FakeTokenHasher(),  # type: ignore[arg-type]
                self.email,
                reset_token_ttl=timedelta(hours=1),
            ),
            _abort,
        )


def _command(**overrides: str) -> ProvisionTenantCommand:
    fields = {
        "name": "Orient LPG Agency",
        "slug": "orient-lpg",
        "primary_contact_email": "ops@orient.example",
        "admin_email": "Admin@Orient.Example",
    }
    fields.update(overrides)
    return ProvisionTenantCommand(**fields)


class TestProvisionTenant:
    async def test_creates_the_tenant_then_its_first_admin(self) -> None:
        harness = _Harness()

        result = await harness.use_case.execute(_command())

        assert result.tenant.slug == "orient-lpg"
        assert result.tenant.status == "trial"
        assert result.admin.role == FIRST_ADMIN_ROLE
        assert result.admin.tenant_id == result.tenant.id
        assert result.admin.email == "admin@orient.example"
        assert harness.aborted == []

    async def test_commits_the_tenant_before_inviting_the_admin(self) -> None:
        harness = _Harness()

        await harness.use_case.execute(_command())

        assert harness.calls.log == ["tenant.add", "uow.commit", "staff.add"]

    async def test_returns_the_raw_setup_token_but_stores_only_its_hash(self) -> None:
        harness = _Harness()

        result = await harness.use_case.execute(_command())

        assert result.setup_token
        assert [t.token_hash for t in harness.reset_tokens.saved] == [
            f"hashed:{result.setup_token}"
        ]
        assert result.setup_token not in {t.token_hash for t in harness.reset_tokens.saved}

    async def test_rejects_an_invalid_slug_before_writing_anything(self) -> None:
        harness = _Harness()

        with pytest.raises(InvariantViolation):
            await harness.use_case.execute(_command(slug="Not Valid!"))

        assert harness.calls.log == []

    async def test_rejects_a_taken_admin_email_before_writing_anything(self) -> None:
        harness = _Harness(existing_emails={"admin@orient.example"})

        with pytest.raises(ConflictError):
            await harness.use_case.execute(_command())

        assert harness.calls.log == []

    async def test_closes_the_half_created_tenant_when_the_invite_fails(self) -> None:
        harness = _Harness(invite_fails=True)

        with pytest.raises(RuntimeError, match="database went away"):
            await harness.use_case.execute(_command())

        assert harness.calls.log == ["tenant.add", "uow.commit", "staff.add", "abort"]
        assert harness.aborted == [harness.tenants.added[0].id]
