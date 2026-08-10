"""`Tenant` domain aggregate — no database required."""

from __future__ import annotations

import uuid

import pytest

from lpg.domain.common.base import InvariantViolation
from lpg.domain.tenant.tenant import Tenant, TenantRenamed, TenantStatusChanged


def _make_tenant(**overrides: object) -> Tenant:
    defaults: dict[str, object] = {
        "name": "Sunrise Gas Agency",
        "slug": "sunrise-gas",
        "primary_contact_email": "ops@sunrise-gas.example",
    }
    defaults.update(overrides)
    return Tenant(uuid.uuid4(), defaults.pop("name"), defaults.pop("slug"), **defaults)  # type: ignore[arg-type]


class TestConstruction:
    def test_defaults_to_trial_status_and_standard_plan(self) -> None:
        tenant = _make_tenant()

        assert tenant.status == "trial"
        assert tenant.subscription_plan == "standard"
        assert tenant.country == "IN"


class TestRename:
    def test_changes_the_name_and_records_an_event(self) -> None:
        tenant = _make_tenant()

        tenant.rename("New Name")

        assert tenant.name == "New Name"
        assert [type(e) for e in tenant.events] == [TenantRenamed]

    def test_rejects_an_empty_name(self) -> None:
        tenant = _make_tenant()

        with pytest.raises(InvariantViolation):
            tenant.rename("   ")


class TestLifecycle:
    def test_activate_moves_trial_to_active(self) -> None:
        tenant = _make_tenant()

        tenant.activate()

        assert tenant.status == "active"
        assert [type(e) for e in tenant.events] == [TenantStatusChanged]

    def test_activate_rejects_a_non_trial_tenant(self) -> None:
        tenant = _make_tenant(status="active")

        with pytest.raises(InvariantViolation):
            tenant.activate()

    def test_suspend_moves_active_to_suspended(self) -> None:
        tenant = _make_tenant(status="active")

        tenant.suspend()

        assert tenant.status == "suspended"

    def test_suspend_rejects_a_trial_tenant(self) -> None:
        tenant = _make_tenant(status="trial")

        with pytest.raises(InvariantViolation):
            tenant.suspend()

    def test_reactivate_moves_suspended_back_to_active(self) -> None:
        tenant = _make_tenant(status="suspended")

        tenant.reactivate()

        assert tenant.status == "active"

    def test_reactivate_rejects_an_already_active_tenant(self) -> None:
        tenant = _make_tenant(status="active")

        with pytest.raises(InvariantViolation):
            tenant.reactivate()

    @pytest.mark.parametrize("status", ["trial", "active", "suspended"])
    def test_close_is_reachable_from_every_non_terminal_status(self, status: str) -> None:
        tenant = _make_tenant(status=status)

        tenant.close()

        assert tenant.status == "closed"

    def test_close_is_terminal(self) -> None:
        tenant = _make_tenant(status="closed")

        with pytest.raises(InvariantViolation):
            tenant.close()

    def test_a_closed_tenant_cannot_be_reactivated(self) -> None:
        tenant = _make_tenant(status="closed")

        with pytest.raises(InvariantViolation):
            tenant.reactivate()

    def test_status_change_event_carries_old_and_new_status(self) -> None:
        tenant = _make_tenant(status="active")

        tenant.suspend()

        (event,) = tenant.events
        assert isinstance(event, TenantStatusChanged)
        assert event.old_status == "active"
        assert event.new_status == "suspended"
