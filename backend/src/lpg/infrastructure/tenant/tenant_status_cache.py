"""`RedisTenantStatusChecker` implements `application/tenant/status.py
::TenantStatusChecker` — mirrors `infrastructure/license/
license_status_cache.py::RedisLicenseStatusChecker` exactly (same TTL, same
cache-failure-degrades-to-DB-read philosophy, same reason for reading
through a `SECURITY DEFINER` function rather than the RLS-scoped
`TenantRepository`: `LoginUseCase`/`RefreshTokenUseCase` run before any
tenant context exists, so no `app.current_tenant_id` session variable is
available yet).

A cache-read failure (Redis unreachable) is treated identically to a cache
miss and falls through to the database — Redis is a performance layer here,
never a hard dependency for correctness.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import text

from lpg.config.logging import get_logger

if TYPE_CHECKING:
    import uuid

    from lpg.application.common.ports import CacheClient
    from lpg.infrastructure.persistence.database import Database

_logger = get_logger(__name__)
_CACHE_TTL_SECONDS = 60

# A tenant row that no longer resolves (should not happen in practice — a
# JWT's tenant_id always came from a real tenant at issuance) fails closed,
# not open: "closed" is exactly the status this codebase's own enforcement
# treats as blocking, the same posture a security check should default to
# for "this tenant doesn't exist" as it does for "this tenant was closed".
_MISSING_TENANT_STATUS = "closed"


def _cache_key(tenant_id: uuid.UUID) -> str:
    return f"tenant:{tenant_id}:status"


class RedisTenantStatusChecker:
    def __init__(self, cache: CacheClient, database: Database) -> None:
        self._cache = cache
        self._database = database

    async def get_status(self, tenant_id: uuid.UUID) -> str:
        key = _cache_key(tenant_id)

        try:
            cached = await self._cache.get(key)
        except Exception as exc:  # noqa: BLE001 - a cache outage degrades to a DB read
            _logger.warning(
                "tenant_status_cache_read_failed", tenant_id=str(tenant_id), error=str(exc)
            )
            cached = None

        if cached is not None:
            return cached

        status = await self._compute_status(tenant_id)

        try:
            await self._cache.set(key, status, ttl_seconds=_CACHE_TTL_SECONDS)
        except Exception as exc:  # noqa: BLE001 - caching is best-effort, never blocks the result
            _logger.warning(
                "tenant_status_cache_write_failed", tenant_id=str(tenant_id), error=str(exc)
            )

        return status

    async def invalidate(self, tenant_id: uuid.UUID) -> None:
        try:
            await self._cache.delete(_cache_key(tenant_id))
        except Exception as exc:  # noqa: BLE001 - best-effort; the TTL still expires it either way
            _logger.warning(
                "tenant_status_cache_invalidate_failed", tenant_id=str(tenant_id), error=str(exc)
            )

    async def _compute_status(self, tenant_id: uuid.UUID) -> str:
        async for session in self._database.session():
            result = await session.execute(
                text("SELECT tenant.tenant_find_status_by_id(:tenant_id)"),
                {"tenant_id": str(tenant_id)},
            )
            status = result.scalar_one()
            return status if status is not None else _MISSING_TENANT_STATUS
        return _MISSING_TENANT_STATUS  # pragma: no cover - session() yields once
