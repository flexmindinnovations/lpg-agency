"""`RedisLicenseStatusChecker` implements `application/license/ports.py
::LicenseStatusChecker` — the **first production use of `RedisCacheClient`**
(`infrastructure/redis/cache.py`). That class has existed since Phase 6 but
was never wired into any dependency provider before this.

`platform.license` is a normal RLS-scoped tenant table (see migration
`92e48f9bf322`'s docstring) — but this checker is used by
`LoginUseCase`/`RefreshTokenUseCase`, which run before any tenant context or
`UnitOfWork` exists (see `application/identity/login.py`'s module
docstring), so no `app.current_tenant_id` session variable is available yet
for RLS to key off. Reads through `platform.license_find_by_tenant_id(uuid)`
— a narrow `SECURITY DEFINER` function, the exact same chicken-and-egg
resolution `identity.identity_user`'s own RLS policy already needed
(`SqlAlchemyIdentityUserRepository`) — rather than depending on
`LicenseRepository`, whose `SqlAlchemyLicenseRepository` implementation
*does* rely on that session variable and is only usable post-auth.

A cache-read failure (Redis unreachable) is treated identically to a cache
miss and falls through to the database — Redis is a performance layer here,
never a hard dependency for correctness. License enforcement stays solid
through a Redis outage, just slower.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import text

from lpg.config.logging import get_logger
from lpg.domain.license.license import License, LicenseLifecycleState

if TYPE_CHECKING:
    import uuid
    from typing import Any

    from sqlalchemy.engine import Row

    from lpg.application.common.ports import CacheClient
    from lpg.infrastructure.persistence.database import Database

_logger = get_logger(__name__)
_CACHE_TTL_SECONDS = 60


def _cache_key(tenant_id: uuid.UUID) -> str:
    return f"tenant:{tenant_id}:license:status"


def _row_to_license(row: Row[Any]) -> License | None:
    if row.id is None:
        return None
    return License(
        row.id,
        row.tenant_id,
        row.key_hash,
        row.key_prefix,
        row.plan_tier,
        timedelta(seconds=row.validity_period_seconds),
        row.issued_at,
        device_caps=dict(row.device_caps or {}),
        activated_at=row.activated_at,
        revoked_at=row.revoked_at,
        version=row.version,
    )


class RedisLicenseStatusChecker:
    def __init__(self, cache: CacheClient, database: Database) -> None:
        self._cache = cache
        self._database = database

    async def get_status(self, tenant_id: uuid.UUID) -> LicenseLifecycleState:
        key = _cache_key(tenant_id)

        try:
            cached = await self._cache.get(key)
        except Exception as exc:  # noqa: BLE001 - a cache outage degrades to a DB read
            _logger.warning(
                "license_status_cache_read_failed", tenant_id=str(tenant_id), error=str(exc)
            )
            cached = None

        if cached is not None:
            return LicenseLifecycleState(cached)

        status = await self._compute_status(tenant_id)

        try:
            await self._cache.set(key, status.value, ttl_seconds=_CACHE_TTL_SECONDS)
        except Exception as exc:  # noqa: BLE001 - caching is best-effort, never blocks the result
            _logger.warning(
                "license_status_cache_write_failed", tenant_id=str(tenant_id), error=str(exc)
            )

        return status

    async def invalidate(self, tenant_id: uuid.UUID) -> None:
        try:
            await self._cache.delete(_cache_key(tenant_id))
        except Exception as exc:  # noqa: BLE001 - best-effort; the TTL still expires it either way
            _logger.warning(
                "license_status_cache_invalidate_failed", tenant_id=str(tenant_id), error=str(exc)
            )

    async def _compute_status(self, tenant_id: uuid.UUID) -> LicenseLifecycleState:
        async for session in self._database.session():
            result = await session.execute(
                text("SELECT * FROM platform.license_find_by_tenant_id(:tenant_id)"),
                {"tenant_id": str(tenant_id)},
            )
            license_ = _row_to_license(result.one())
            if license_ is None:
                return LicenseLifecycleState.PENDING_ACTIVATION
            return license_.compute_status(at=datetime.now(UTC))
        return LicenseLifecycleState.PENDING_ACTIVATION  # pragma: no cover - session() yields once
