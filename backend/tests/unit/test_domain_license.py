"""`License`/`LicenseFeatureOverride`/`LicenseEntitlementService`/
`LinkedDevice` — no database required.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from lpg.domain.common.base import InvariantViolation
from lpg.domain.license.license import (
    License,
    LicenseEntitlementService,
    LicenseFeatureOverride,
    LicenseLifecycleState,
)
from lpg.domain.license.linked_device import LinkedDevice

_TENANT_A = uuid.UUID("11111111-1111-1111-1111-111111111111")
_ONE_YEAR = timedelta(days=365)


def _license(
    *,
    plan_tier: str = "standard",
    validity_period: timedelta = _ONE_YEAR,
    device_caps: dict[str, int | None] | None = None,
    activated_at: datetime | None = None,
    revoked_at: datetime | None = None,
) -> License:
    return License(
        uuid.uuid4(),
        _TENANT_A,
        "hash",
        "LPG-ABCD",
        plan_tier,
        validity_period,
        datetime.now(UTC),
        device_caps=device_caps,
        activated_at=activated_at,
        revoked_at=revoked_at,
    )


class TestLicenseConstruction:
    def test_rejects_an_unrecognized_plan_tier(self) -> None:
        with pytest.raises(InvariantViolation):
            _license(plan_tier="enterprise_deluxe")

    def test_rejects_an_unrecognized_app_type_in_device_caps(self) -> None:
        with pytest.raises(InvariantViolation):
            _license(device_caps={"smart_fridge_app": 5})

    def test_accepts_a_recognized_plan_tier_and_device_caps(self) -> None:
        license_ = _license(plan_tier="premium", device_caps={"driver_app": 10})

        assert license_.plan_tier == "premium"
        assert license_.device_caps == {"driver_app": 10}


class TestLicenseActivation:
    def test_activating_a_pending_license_sets_activated_at(self) -> None:
        license_ = _license()
        now = datetime.now(UTC)

        license_.activate(at=now)

        assert license_.activated_at == now

    def test_activating_an_already_activated_license_raises(self) -> None:
        license_ = _license(activated_at=datetime.now(UTC))

        with pytest.raises(InvariantViolation):
            license_.activate(at=datetime.now(UTC))

    def test_activating_a_revoked_license_raises(self) -> None:
        license_ = _license(revoked_at=datetime.now(UTC))

        with pytest.raises(InvariantViolation):
            license_.activate(at=datetime.now(UTC))

    def test_revoking_an_already_revoked_license_raises(self) -> None:
        license_ = _license(revoked_at=datetime.now(UTC))

        with pytest.raises(InvariantViolation):
            license_.revoke(at=datetime.now(UTC))


class TestLicenseStatusComputation:
    def test_a_never_activated_license_is_pending_activation(self) -> None:
        license_ = _license()

        assert license_.compute_status(at=datetime.now(UTC)) == (
            LicenseLifecycleState.PENDING_ACTIVATION
        )

    def test_a_revoked_license_is_revoked_regardless_of_dates(self) -> None:
        activated_at = datetime.now(UTC) - timedelta(days=1000)
        license_ = _license(
            validity_period=_ONE_YEAR, activated_at=activated_at, revoked_at=datetime.now(UTC)
        )

        assert license_.compute_status(at=datetime.now(UTC)) == LicenseLifecycleState.REVOKED

    def test_immediately_after_activation_the_license_is_active(self) -> None:
        activated_at = datetime.now(UTC)
        license_ = _license(validity_period=timedelta(days=30), activated_at=activated_at)

        assert license_.compute_status(at=activated_at) == LicenseLifecycleState.ACTIVE

    def test_one_second_before_expiry_the_license_is_still_active(self) -> None:
        activated_at = datetime.now(UTC)
        validity = timedelta(days=30)
        license_ = _license(validity_period=validity, activated_at=activated_at)
        expires_at = activated_at + validity

        status = license_.compute_status(at=expires_at - timedelta(seconds=1))

        assert status == LicenseLifecycleState.ACTIVE

    def test_exactly_at_expiry_the_license_enters_grace(self) -> None:
        activated_at = datetime.now(UTC)
        validity = timedelta(days=30)
        license_ = _license(validity_period=validity, activated_at=activated_at)
        expires_at = activated_at + validity

        assert license_.compute_status(at=expires_at) == LicenseLifecycleState.GRACE

    def test_one_second_before_grace_ends_the_license_is_still_in_grace(self) -> None:
        activated_at = datetime.now(UTC)
        validity = timedelta(days=30)
        license_ = _license(validity_period=validity, activated_at=activated_at)
        grace_ends_at = activated_at + validity + timedelta(days=1)

        status = license_.compute_status(at=grace_ends_at - timedelta(seconds=1))

        assert status == LicenseLifecycleState.GRACE

    def test_exactly_when_grace_ends_the_license_is_blocked(self) -> None:
        activated_at = datetime.now(UTC)
        validity = timedelta(days=30)
        license_ = _license(validity_period=validity, activated_at=activated_at)
        grace_ends_at = activated_at + validity + timedelta(days=1)

        assert license_.compute_status(at=grace_ends_at) == LicenseLifecycleState.BLOCKED

    def test_well_past_grace_the_license_stays_blocked(self) -> None:
        activated_at = datetime.now(UTC) - timedelta(days=400)
        license_ = _license(validity_period=timedelta(days=30), activated_at=activated_at)

        assert license_.compute_status(at=datetime.now(UTC)) == LicenseLifecycleState.BLOCKED

    def test_expires_at_and_grace_ends_at_are_none_before_activation(self) -> None:
        license_ = _license()

        assert license_.expires_at is None
        assert license_.grace_ends_at is None

    def test_expires_at_and_grace_ends_at_are_derived_from_activation(self) -> None:
        activated_at = datetime.now(UTC)
        validity = timedelta(days=30)
        license_ = _license(validity_period=validity, activated_at=activated_at)

        assert license_.expires_at == activated_at + validity
        assert license_.grace_ends_at == activated_at + validity + timedelta(days=1)


class TestLicenseDeviceLimit:
    def test_an_unset_cap_is_unlimited(self) -> None:
        license_ = _license(device_caps={})

        assert license_.is_within_device_limit("driver_app", 10_000) is True

    def test_a_count_under_the_cap_is_within_limit(self) -> None:
        license_ = _license(device_caps={"driver_app": 5})

        assert license_.is_within_device_limit("driver_app", 4) is True

    def test_a_count_at_the_cap_is_not_within_limit(self) -> None:
        license_ = _license(device_caps={"driver_app": 5})

        assert license_.is_within_device_limit("driver_app", 5) is False

    def test_a_count_over_the_cap_is_not_within_limit(self) -> None:
        license_ = _license(device_caps={"driver_app": 5})

        assert license_.is_within_device_limit("driver_app", 6) is False

    def test_set_device_cap_rejects_an_unrecognized_app_type(self) -> None:
        license_ = _license()

        with pytest.raises(InvariantViolation):
            license_.set_device_cap("smart_fridge_app", 5)

    def test_set_plan_tier_rejects_an_unrecognized_tier(self) -> None:
        license_ = _license()

        with pytest.raises(InvariantViolation):
            license_.set_plan_tier("enterprise_deluxe")


class TestLicenseEntitlementService:
    def test_a_feature_in_the_tier_catalog_is_granted_with_no_override(self) -> None:
        license_ = _license(plan_tier="basic")

        result = LicenseEntitlementService.is_feature_granted(license_, [], "module_orders")

        assert result is True

    def test_a_feature_outside_the_tier_catalog_is_not_granted_with_no_override(self) -> None:
        license_ = _license(plan_tier="basic")

        result = LicenseEntitlementService.is_feature_granted(license_, [], "module_reporting")

        assert result is False

    def test_an_enabling_override_wins_even_outside_the_tier_catalog(self) -> None:
        license_ = _license(plan_tier="basic")
        override = LicenseFeatureOverride(
            uuid.uuid4(), license_.id, "module_reporting", granted=True
        )

        result = LicenseEntitlementService.is_feature_granted(
            license_, [override], "module_reporting"
        )

        assert result is True

    def test_a_disabling_override_wins_even_inside_the_tier_catalog(self) -> None:
        license_ = _license(plan_tier="premium")
        override = LicenseFeatureOverride(uuid.uuid4(), license_.id, "module_orders", granted=False)

        result = LicenseEntitlementService.is_feature_granted(
            license_, [override], "module_orders"
        )

        assert result is False


class TestLinkedDeviceConstruction:
    def test_rejects_an_unrecognized_app_type(self) -> None:
        with pytest.raises(InvariantViolation):
            LinkedDevice(
                uuid.uuid4(),
                _TENANT_A,
                uuid.uuid4(),
                "smart_fridge_app",
                "device-123",
                "Test Device",
                datetime.now(UTC),
            )

    def test_a_newly_registered_device_is_active(self) -> None:
        device = LinkedDevice(
            uuid.uuid4(),
            _TENANT_A,
            uuid.uuid4(),
            "driver_app",
            "device-123",
            "Test Device",
            datetime.now(UTC),
        )

        assert device.is_active is True

    def test_revoking_a_device_makes_it_inactive(self) -> None:
        device = LinkedDevice(
            uuid.uuid4(),
            _TENANT_A,
            uuid.uuid4(),
            "driver_app",
            "device-123",
            "Test Device",
            datetime.now(UTC),
        )

        device.revoke(at=datetime.now(UTC))

        assert device.is_active is False

    def test_revoking_an_already_revoked_device_raises(self) -> None:
        device = LinkedDevice(
            uuid.uuid4(),
            _TENANT_A,
            uuid.uuid4(),
            "driver_app",
            "device-123",
            "Test Device",
            datetime.now(UTC),
            revoked_at=datetime.now(UTC),
        )

        with pytest.raises(InvariantViolation):
            device.revoke(at=datetime.now(UTC))

    def test_touch_last_seen_updates_the_timestamp(self) -> None:
        device = LinkedDevice(
            uuid.uuid4(),
            _TENANT_A,
            uuid.uuid4(),
            "driver_app",
            "device-123",
            "Test Device",
            datetime.now(UTC) - timedelta(days=1),
        )
        now = datetime.now(UTC)

        device.touch_last_seen(at=now)

        assert device.last_seen_at == now
