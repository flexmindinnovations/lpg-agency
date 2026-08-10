"""`FeatureFlag` (platform-wide), `FeatureFlagOverride` (tenant-scoped), and
`FeatureFlagService` — the domain service that decides whether a flag is on
for a given tenant.

Grouped in one `platform` bounded context rather than split across
`platform`/`tenant` application modules: a flag and its tenant overrides are
one conceptual capability (a flag definition is meaningless without knowing
how overrides interact with it), even though `FeatureFlagOverride`'s table
happens to live in the `tenant` schema for RLS reasons (see migration
`a7c3e9f5b1d8`). The persistence-schema boundary and the bounded-context
boundary are allowed to differ — the Repository pattern is exactly what
translates between them (`03-backend-architecture.md` §4).
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

from lpg.domain.common.base import AggregateRoot, InvariantViolation

if TYPE_CHECKING:
    import uuid
    from datetime import datetime


class FeatureFlag(AggregateRoot):
    """A platform-wide flag definition. `key` is both the natural key and
    the identity — there is no separate surrogate UUID; `AggregateRoot`
    accepts any hashable id, and every caller already thinks in terms of the
    key string, not a UUID nobody would otherwise reference.
    """

    __slots__ = (
        "_description",
        "_ends_at",
        "_is_enabled_by_default",
        "_key",
        "_rollout_percentage",
        "_starts_at",
    )

    def __init__(
        self,
        key: str,
        description: str,
        *,
        is_enabled_by_default: bool = False,
        rollout_percentage: int | None = None,
        starts_at: datetime | None = None,
        ends_at: datetime | None = None,
        version: int = 1,
    ) -> None:
        super().__init__(key, version=version)  # type: ignore[arg-type]
        if rollout_percentage is not None and not (0 <= rollout_percentage <= 100):
            msg = "Rollout percentage must be between 0 and 100."
            raise InvariantViolation(msg, key=key)
        if starts_at is not None and ends_at is not None and starts_at >= ends_at:
            msg = "A flag's start time must be before its end time."
            raise InvariantViolation(msg, key=key)

        self._key = key
        self._description = description
        self._is_enabled_by_default = is_enabled_by_default
        self._rollout_percentage = rollout_percentage
        self._starts_at = starts_at
        self._ends_at = ends_at

    @property
    def key(self) -> str:
        return self._key

    @property
    def description(self) -> str:
        return self._description

    @property
    def is_enabled_by_default(self) -> bool:
        return self._is_enabled_by_default

    @property
    def rollout_percentage(self) -> int | None:
        return self._rollout_percentage

    @property
    def starts_at(self) -> datetime | None:
        return self._starts_at

    @property
    def ends_at(self) -> datetime | None:
        return self._ends_at

    def set_enabled_by_default(self, *, enabled: bool) -> None:
        self._is_enabled_by_default = enabled

    def set_rollout_percentage(self, percentage: int | None) -> None:
        if percentage is not None and not (0 <= percentage <= 100):
            msg = "Rollout percentage must be between 0 and 100."
            raise InvariantViolation(msg, key=self._key)
        self._rollout_percentage = percentage

    def schedule(self, *, starts_at: datetime | None, ends_at: datetime | None) -> None:
        if starts_at is not None and ends_at is not None and starts_at >= ends_at:
            msg = "A flag's start time must be before its end time."
            raise InvariantViolation(msg, key=self._key)
        self._starts_at = starts_at
        self._ends_at = ends_at


class FeatureFlagOverride(AggregateRoot):
    """One tenant's explicit override of a platform flag — always wins over
    the platform default/rollout when present (`FeatureFlagService.is_enabled`).
    """

    __slots__ = ("_flag_key", "_is_enabled", "_tenant_id")

    def __init__(
        self,
        override_id: uuid.UUID,
        tenant_id: uuid.UUID,
        flag_key: str,
        *,
        is_enabled: bool,
        version: int = 1,
    ) -> None:
        super().__init__(override_id, version=version)
        self._tenant_id = tenant_id
        self._flag_key = flag_key
        self._is_enabled = is_enabled

    @property
    def tenant_id(self) -> uuid.UUID:
        return self._tenant_id

    @property
    def flag_key(self) -> str:
        return self._flag_key

    @property
    def is_enabled(self) -> bool:
        return self._is_enabled

    def set_enabled(self, *, enabled: bool) -> None:
        self._is_enabled = enabled


def _rollout_bucket(tenant_id: uuid.UUID) -> int:
    """A stable 0-99 bucket for a tenant, independent of Python's per-process
    hash randomization (`hash()` on a `str`/`bytes` varies by
    `PYTHONHASHSEED` run to run — a rollout bucket that changed between
    process restarts would silently flip tenants in and out of a rollout).
    Rollout is per-tenant, not per-end-user, since this is a B2B SaaS
    platform — gradually rolling a feature out to a percentage of *tenants*
    is the meaningful unit here, not individual users within one.
    """
    digest = hashlib.sha256(str(tenant_id).encode("utf-8")).hexdigest()
    return int(digest, 16) % 100


class FeatureFlagService:
    """Decides whether a flag is enabled for a tenant, at a point in time.

    Precedence: schedule (not yet started / already ended -> off) -> explicit
    tenant override (always wins if present) -> platform default -> rollout
    percentage.
    """

    @staticmethod
    def is_enabled(
        flag: FeatureFlag | None,
        override: FeatureFlagOverride | None,
        tenant_id: uuid.UUID,
        *,
        at: datetime,
    ) -> bool:
        if flag is None:
            return False  # Fail closed — an unknown flag is off, never on.

        if flag.starts_at is not None and at < flag.starts_at:
            return False
        if flag.ends_at is not None and at >= flag.ends_at:
            return False

        if override is not None:
            return override.is_enabled

        if not flag.is_enabled_by_default:
            return False

        if flag.rollout_percentage is None or flag.rollout_percentage >= 100:
            return True

        return _rollout_bucket(tenant_id) < flag.rollout_percentage
