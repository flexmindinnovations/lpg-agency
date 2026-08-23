"""`License` (per-tenant activation key), `LicenseFeatureOverride`
(super_admin-only entitlement override), and `LicenseEntitlementService` —
grouped in one file for the same reason `platform/feature_flag.py` groups
`FeatureFlag`/`FeatureFlagOverride`/`FeatureFlagService`: a license and its
entitlement overrides are one conceptual capability.

`License` is a normal RLS-scoped tenant table (migration `92e48f9bf322`),
despite living in the `platform` schema for persistence-location reasons —
see that migration's module docstring for why. The one place RLS can't
apply — `LoginUseCase`/`RefreshTokenUseCase` reading a license before any
tenant context exists — goes through a narrow `SECURITY DEFINER` SQL
function instead (`RedisLicenseStatusChecker`), the same resolution
`identity.identity_user`'s own RLS policy already needed.

The entitlement layer here is deliberately independent of
`platform.feature_flag`'s `FeatureFlagOverride` — `agency_admin` already
holds `feature_flags:manage_tenant` (write access to that table). If plan
entitlement reused it, a tenant admin could self-grant a feature their plan
doesn't include. `LicenseFeatureOverride` is written by `super_admin` only,
live-checked, exactly like `feature_flags:manage_platform`.
"""

from __future__ import annotations

from datetime import timedelta
from enum import StrEnum
from typing import TYPE_CHECKING

from lpg.domain.common.base import AggregateRoot, InvariantViolation

if TYPE_CHECKING:
    import uuid
    from collections.abc import Sequence
    from datetime import datetime

#: Full access continues for this long past expiry before a hard lockout —
#: a tenant is never surprised into a lockout with zero warning.
GRACE_PERIOD = timedelta(days=1)

#: The fixed set of client app types this phase recognizes — mirrors
#: `RECOGNIZED_CONFIG_KEYS`'s fixed-catalog-in-code approach. Dashboard is
#: deliberately absent: it's a browser session under the existing JWT model,
#: not a distinct installed app instance that needs linking.
RECOGNIZED_APP_TYPES = frozenset({"customer_app", "driver_app", "warehouse_app"})

#: Which feature keys a plan tier grants by default. A `LicenseFeatureOverride`
#: on a specific license always wins over this default (`LicenseEntitlementService`).
#: Deliberately a minimal starter catalog — the consumer that actually gates
#: UI/API access on these keys (e.g. sidebar module visibility) is future work;
#: this catalog only needs to be structurally correct today, not exhaustive.
PLAN_TIER_FEATURE_CATALOG: dict[str, frozenset[str]] = {
    "basic": frozenset({"module_orders", "module_inventory"}),
    "standard": frozenset(
        {"module_orders", "module_inventory", "module_dispatch", "module_invoicing"}
    ),
    "premium": frozenset(
        {
            "module_orders",
            "module_inventory",
            "module_dispatch",
            "module_invoicing",
            "module_reporting",
            "module_complaints",
        }
    ),
}


class LicenseLifecycleState(StrEnum):
    """`License.compute_status`'s result — a pure function of `activated_at`/
    `revoked_at` against `at`, never a stored column, so there is nothing to
    keep in sync and no sweep job is required for correctness."""

    PENDING_ACTIVATION = "pending_activation"
    ACTIVE = "active"
    GRACE = "grace"
    BLOCKED = "blocked"
    REVOKED = "revoked"


class License(AggregateRoot):
    """One tenant's activation key. `key_hash` is the only form of the key
    this aggregate ever holds — the plaintext exists solely inside
    `IssueLicenseUseCase` and the one response DTO that echoes it back once.
    """

    __slots__ = (
        "_activated_at",
        "_device_caps",
        "_issued_at",
        "_key_hash",
        "_key_prefix",
        "_plan_tier",
        "_revoked_at",
        "_tenant_id",
        "_validity_period",
    )

    def __init__(
        self,
        license_id: uuid.UUID,
        tenant_id: uuid.UUID,
        key_hash: str,
        key_prefix: str,
        plan_tier: str,
        validity_period: timedelta,
        issued_at: datetime,
        *,
        device_caps: dict[str, int | None] | None = None,
        activated_at: datetime | None = None,
        revoked_at: datetime | None = None,
        version: int = 1,
    ) -> None:
        super().__init__(license_id, version=version)
        if plan_tier not in PLAN_TIER_FEATURE_CATALOG:
            msg = f"'{plan_tier}' is not a recognized plan tier."
            raise InvariantViolation(msg, plan_tier=plan_tier)

        resolved_caps = dict(device_caps) if device_caps else {}
        for app_type in resolved_caps:
            if app_type not in RECOGNIZED_APP_TYPES:
                msg = f"'{app_type}' is not a recognized app type."
                raise InvariantViolation(msg, app_type=app_type)

        self._tenant_id = tenant_id
        self._key_hash = key_hash
        self._key_prefix = key_prefix
        self._plan_tier = plan_tier
        self._validity_period = validity_period
        self._issued_at = issued_at
        self._device_caps = resolved_caps
        self._activated_at = activated_at
        self._revoked_at = revoked_at

    @property
    def tenant_id(self) -> uuid.UUID:
        return self._tenant_id

    @property
    def key_hash(self) -> str:
        return self._key_hash

    @property
    def key_prefix(self) -> str:
        return self._key_prefix

    @property
    def plan_tier(self) -> str:
        return self._plan_tier

    @property
    def validity_period(self) -> timedelta:
        return self._validity_period

    @property
    def issued_at(self) -> datetime:
        return self._issued_at

    @property
    def device_caps(self) -> dict[str, int | None]:
        return dict(self._device_caps)

    @property
    def activated_at(self) -> datetime | None:
        return self._activated_at

    @property
    def revoked_at(self) -> datetime | None:
        return self._revoked_at

    @property
    def expires_at(self) -> datetime | None:
        if self._activated_at is None:
            return None
        return self._activated_at + self._validity_period

    @property
    def grace_ends_at(self) -> datetime | None:
        expires_at = self.expires_at
        if expires_at is None:
            return None
        return expires_at + GRACE_PERIOD

    def activate(self, *, at: datetime) -> None:
        """Marks the license activated. Whether the presented key actually
        matches `key_hash` is verified by the caller (a security-primitive
        comparison via `hmac.compare_digest` belongs at the use-case layer,
        not inside a domain aggregate) — this method only enforces the state
        transition itself is legal."""
        if self._revoked_at is not None:
            msg = "A revoked license cannot be activated."
            raise InvariantViolation(msg, license_id=str(self.id))
        if self._activated_at is not None:
            msg = "This license has already been activated."
            raise InvariantViolation(msg, license_id=str(self.id))
        self._activated_at = at

    def revoke(self, *, at: datetime) -> None:
        if self._revoked_at is not None:
            msg = "This license has already been revoked."
            raise InvariantViolation(msg, license_id=str(self.id))
        self._revoked_at = at

    def compute_status(self, *, at: datetime) -> LicenseLifecycleState:
        if self._revoked_at is not None:
            return LicenseLifecycleState.REVOKED
        if self._activated_at is None:
            return LicenseLifecycleState.PENDING_ACTIVATION

        expires_at = self._activated_at + self._validity_period
        if at < expires_at:
            return LicenseLifecycleState.ACTIVE
        if at < expires_at + GRACE_PERIOD:
            return LicenseLifecycleState.GRACE
        return LicenseLifecycleState.BLOCKED

    def is_within_device_limit(self, app_type: str, current_count: int) -> bool:
        cap = self._device_caps.get(app_type)
        return cap is None or current_count < cap

    def set_plan_tier(self, plan_tier: str) -> None:
        if plan_tier not in PLAN_TIER_FEATURE_CATALOG:
            msg = f"'{plan_tier}' is not a recognized plan tier."
            raise InvariantViolation(msg, plan_tier=plan_tier)
        self._plan_tier = plan_tier

    def set_device_cap(self, app_type: str, max_devices: int | None) -> None:
        if app_type not in RECOGNIZED_APP_TYPES:
            msg = f"'{app_type}' is not a recognized app type."
            raise InvariantViolation(msg, app_type=app_type)
        self._device_caps[app_type] = max_devices


class LicenseFeatureOverride(AggregateRoot):
    """One license's explicit override of its plan tier's default feature
    grant — always wins over `PLAN_TIER_FEATURE_CATALOG` when present
    (`LicenseEntitlementService.is_feature_granted`)."""

    __slots__ = ("_feature_key", "_granted", "_license_id")

    def __init__(
        self,
        override_id: uuid.UUID,
        license_id: uuid.UUID,
        feature_key: str,
        *,
        granted: bool,
        version: int = 1,
    ) -> None:
        super().__init__(override_id, version=version)
        self._license_id = license_id
        self._feature_key = feature_key
        self._granted = granted

    @property
    def license_id(self) -> uuid.UUID:
        return self._license_id

    @property
    def feature_key(self) -> str:
        return self._feature_key

    @property
    def granted(self) -> bool:
        return self._granted

    def set_granted(self, *, granted: bool) -> None:
        self._granted = granted


class LicenseEntitlementService:
    """Resolves whether a license grants a feature key at a point in time.

    Precedence: explicit `LicenseFeatureOverride` (always wins if present) ->
    the plan tier's default catalog. Deliberately does not know about
    `FeatureFlagOverride` — composing "license grants X AND the tenant admin
    hasn't turned X off" is left to a future consumer of this service.
    """

    @staticmethod
    def is_feature_granted(
        license: License,
        overrides: Sequence[LicenseFeatureOverride],
        feature_key: str,
    ) -> bool:
        override = next((o for o in overrides if o.feature_key == feature_key), None)
        if override is not None:
            return override.granted
        return feature_key in PLAN_TIER_FEATURE_CATALOG.get(license.plan_tier, frozenset())
