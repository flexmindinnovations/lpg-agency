"""Super Admin agency-user use cases (Phase 31) - behaviour and failure paths, no database.

The real `InviteStaffUserUseCase` is used for adding an admin (only its
collaborators are faked): its token behaviour is part of what these use cases
return.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest

from lpg.application.common.errors import ConflictError, NotFoundError
from lpg.application.identity.staff_user import InviteStaffUserUseCase
from lpg.application.platform.agency_users import (
    AGENCY_ADMIN_ROLE,
    AddAgencyAdminCommand,
    AddAgencyAdminUseCase,
    IssueSetupLinkCommand,
    IssueSetupLinkUseCase,
    ListAgencyUsersQuery,
    ListAgencyUsersUseCase,
)
from lpg.domain.identity.user import IdentityUser
from lpg.domain.tenant.tenant import Tenant

if TYPE_CHECKING:
    from lpg.domain.identity.password_reset_token import PasswordResetToken

TTL = timedelta(hours=24)


class _Log:
    def __init__(self) -> None:
        self.calls: list[str] = []


class _Tenants:
    def __init__(self, *tenants: Tenant) -> None:
        self._by_id = {t.id: t for t in tenants}

    async def get(self, tenant_id: uuid.UUID) -> Tenant | None:
        return self._by_id.get(tenant_id)


class _Staff:
    def __init__(self, log: _Log, users: list[IdentityUser] | None = None) -> None:
        self._log = log
        self._users = {u.id: u for u in users or []}

    async def get(self, user_id: uuid.UUID) -> IdentityUser | None:
        return self._users.get(user_id)

    async def list_for_tenant(
        self, tenant_id: uuid.UUID, *, exclude_roles: frozenset[str]
    ) -> list[IdentityUser]:
        return [
            u
            for u in self._users.values()
            if u.tenant_id == tenant_id and u.role not in exclude_roles
        ]

    async def add(self, user: IdentityUser) -> None:
        self._log.calls.append("staff.add")
        self._users[user.id] = user


class _UserLookup:
    def __init__(self, taken: set[str] | None = None) -> None:
        self._taken = taken or set()

    async def get_by_email(self, email: str) -> IdentityUser | None:
        if email in self._taken:
            return _user(email=email, tenant_id=uuid.uuid4())
        return None


class _ResetTokens:
    def __init__(self, log: _Log) -> None:
        self._log = log
        self.saved: list[PasswordResetToken] = []
        self.invalidated_for: list[uuid.UUID] = []

    async def save(self, token: PasswordResetToken) -> None:
        self._log.calls.append("token.save")
        self.saved.append(token)

    async def invalidate_unused_for_user(self, user_id: uuid.UUID) -> None:
        self._log.calls.append("token.invalidate")
        self.invalidated_for.append(user_id)


class _Hasher:
    def hash(self, raw: str) -> str:
        return f"hashed:{raw}"


class _Email:
    async def send(self, to: str, subject: str, body: str) -> None:
        del to, subject, body


class _Audit:
    def __init__(self, log: _Log) -> None:
        self._log = log
        self.entries: list[dict[str, object]] = []

    async def record(
        self,
        *,
        action: str,
        entity_name: str,
        entity_id: str,
        entity_display_name: str | None,
        details: dict[str, object],
    ) -> None:
        self._log.calls.append("audit")
        self.entries.append(
            {
                "action": action,
                "entity_name": entity_name,
                "entity_id": entity_id,
                "display": entity_display_name,
                "details": details,
            }
        )


def _agency(*, slug: str = "orient-lpg", closed: bool = False) -> Tenant:
    tenant = Tenant.provision(name="Orient", slug=slug, primary_contact_email="o@example.com")
    if closed:
        tenant.close()
    return tenant


def _user(
    *,
    email: str = "admin@example.com",
    tenant_id: uuid.UUID,
    role: str = AGENCY_ADMIN_ROLE,
    active: bool = True,
) -> IdentityUser:
    return IdentityUser(
        uuid.uuid4(),
        tenant_id=tenant_id,
        branch_id=None,
        email=email,
        phone_number=None,
        password_hash="x",
        role=role,
        is_active=active,
    )


class TestListAgencyUsers:
    async def test_lists_staff_but_not_customers_or_drivers(self) -> None:
        agency, log = _agency(), _Log()
        staff = _Staff(
            log,
            [
                _user(email="a@example.com", tenant_id=agency.id),
                _user(email="m@example.com", tenant_id=agency.id, role="manager"),
                _user(email="c@example.com", tenant_id=agency.id, role="customer"),
                _user(email="d@example.com", tenant_id=agency.id, role="driver"),
            ],
        )

        users = await ListAgencyUsersUseCase(_Tenants(agency), staff).execute(  # type: ignore[arg-type]
            ListAgencyUsersQuery(tenant_id=agency.id)
        )

        assert {u.email for u in users} == {"a@example.com", "m@example.com"}

    async def test_unknown_agency_is_not_found(self) -> None:
        with pytest.raises(NotFoundError):
            await ListAgencyUsersUseCase(_Tenants(), _Staff(_Log())).execute(  # type: ignore[arg-type]
                ListAgencyUsersQuery(tenant_id=uuid.uuid4())
            )

    async def test_a_closed_agency_can_still_be_read(self) -> None:
        agency = _agency(closed=True)

        users = await ListAgencyUsersUseCase(_Tenants(agency), _Staff(_Log())).execute(  # type: ignore[arg-type]
            ListAgencyUsersQuery(tenant_id=agency.id)
        )

        assert list(users) == []


class _AddHarness:
    def __init__(self, agency: Tenant, *, taken: set[str] | None = None) -> None:
        self.log = _Log()
        self.staff = _Staff(self.log)
        self.tokens = _ResetTokens(self.log)
        self.audit = _Audit(self.log)
        invite = InviteStaffUserUseCase(
            self.staff,  # type: ignore[arg-type]
            self.tokens,  # type: ignore[arg-type]
            _Hasher(),  # type: ignore[arg-type]
            _Email(),
            reset_token_ttl=TTL,
        )
        self.use_case = AddAgencyAdminUseCase(
            _Tenants(agency),  # type: ignore[arg-type]
            _UserLookup(taken),  # type: ignore[arg-type]
            invite,
            self.audit,
        )


class TestAddAgencyAdmin:
    async def test_creates_an_agency_admin_and_returns_a_setup_link(self) -> None:
        agency = _agency()
        harness = _AddHarness(agency)

        issued = await harness.use_case.execute(
            AddAgencyAdminCommand(tenant_id=agency.id, email="  New.Admin@Example.com ")
        )

        assert issued.user.role == AGENCY_ADMIN_ROLE
        assert issued.user.tenant_id == agency.id
        assert issued.user.email == "new.admin@example.com"
        assert issued.setup_token
        assert harness.tokens.saved[0].token_hash == f"hashed:{issued.setup_token}"
        assert issued.setup_token_expires_at - datetime.now(UTC) <= TTL

    async def test_records_an_audit_entry_that_never_contains_the_token(self) -> None:
        agency = _agency()
        harness = _AddHarness(agency)

        issued = await harness.use_case.execute(
            AddAgencyAdminCommand(tenant_id=agency.id, email="new@example.com")
        )

        [entry] = harness.audit.entries
        assert entry["action"] == "platform.agency_admin_added"
        assert entry["entity_id"] == str(issued.user.id)
        assert issued.setup_token not in repr(entry)

    async def test_a_taken_email_is_a_conflict_and_changes_nothing(self) -> None:
        agency = _agency()
        harness = _AddHarness(agency, taken={"taken@example.com"})

        with pytest.raises(ConflictError, match="already exists"):
            await harness.use_case.execute(
                AddAgencyAdminCommand(tenant_id=agency.id, email="Taken@Example.com")
            )

        assert harness.log.calls == []

    async def test_a_closed_agency_is_a_conflict(self) -> None:
        agency = _agency(closed=True)
        harness = _AddHarness(agency)

        with pytest.raises(ConflictError, match="closed"):
            await harness.use_case.execute(
                AddAgencyAdminCommand(tenant_id=agency.id, email="a@example.com")
            )

        assert harness.log.calls == []

    async def test_an_unknown_agency_is_not_found(self) -> None:
        harness = _AddHarness(_agency())

        with pytest.raises(NotFoundError):
            await harness.use_case.execute(
                AddAgencyAdminCommand(tenant_id=uuid.uuid4(), email="a@example.com")
            )


class _LinkHarness:
    def __init__(self, agency: Tenant, users: list[IdentityUser]) -> None:
        self.log = _Log()
        self.tokens = _ResetTokens(self.log)
        self.audit = _Audit(self.log)
        self.use_case = IssueSetupLinkUseCase(
            _Tenants(agency),  # type: ignore[arg-type]
            _Staff(self.log, users),  # type: ignore[arg-type]
            self.tokens,  # type: ignore[arg-type]
            _Hasher(),  # type: ignore[arg-type]
            self.audit,
            link_ttl=TTL,
        )


class TestIssueSetupLink:
    async def test_invalidates_older_links_before_saving_the_new_one_then_audits(self) -> None:
        agency = _agency()
        admin = _user(tenant_id=agency.id)
        harness = _LinkHarness(agency, [admin])

        issued = await harness.use_case.execute(
            IssueSetupLinkCommand(tenant_id=agency.id, user_id=admin.id)
        )

        assert harness.log.calls == ["token.invalidate", "token.save", "audit"]
        assert harness.tokens.invalidated_for == [admin.id]
        assert harness.tokens.saved[0].token_hash == f"hashed:{issued.setup_token}"
        assert timedelta(hours=23) < issued.setup_token_expires_at - datetime.now(UTC) <= TTL

    async def test_audit_entry_never_contains_the_token(self) -> None:
        agency = _agency()
        admin = _user(tenant_id=agency.id)
        harness = _LinkHarness(agency, [admin])

        issued = await harness.use_case.execute(
            IssueSetupLinkCommand(tenant_id=agency.id, user_id=admin.id)
        )

        [entry] = harness.audit.entries
        assert entry["action"] == "platform.setup_link_issued"
        assert issued.setup_token not in repr(entry)

    async def test_a_user_of_another_agency_is_not_found(self) -> None:
        agency, other = _agency(), _agency(slug="other-agency")
        stranger = _user(tenant_id=other.id)
        harness = _LinkHarness(agency, [stranger])

        with pytest.raises(NotFoundError):
            await harness.use_case.execute(
                IssueSetupLinkCommand(tenant_id=agency.id, user_id=stranger.id)
            )

        assert harness.log.calls == []

    async def test_only_agency_admins_can_be_recovered(self) -> None:
        agency = _agency()
        manager = _user(tenant_id=agency.id, role="manager")
        harness = _LinkHarness(agency, [manager])

        with pytest.raises(ConflictError, match="agency admin"):
            await harness.use_case.execute(
                IssueSetupLinkCommand(tenant_id=agency.id, user_id=manager.id)
            )

        assert harness.log.calls == []

    async def test_a_deactivated_admin_is_refused(self) -> None:
        agency = _agency()
        admin = _user(tenant_id=agency.id, active=False)
        harness = _LinkHarness(agency, [admin])

        with pytest.raises(ConflictError, match="deactivated"):
            await harness.use_case.execute(
                IssueSetupLinkCommand(tenant_id=agency.id, user_id=admin.id)
            )

    async def test_a_closed_agency_is_refused(self) -> None:
        agency = _agency(closed=True)
        admin = _user(tenant_id=agency.id)
        harness = _LinkHarness(agency, [admin])

        with pytest.raises(ConflictError, match="closed"):
            await harness.use_case.execute(
                IssueSetupLinkCommand(tenant_id=agency.id, user_id=admin.id)
            )
