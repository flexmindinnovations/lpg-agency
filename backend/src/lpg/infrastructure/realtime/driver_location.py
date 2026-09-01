"""Redis-backed ``DriverLocationStore`` — the last-known driver position for a
route, held for ``_TTL_SECONDS`` so a customer opening the tracking screen
between pings still gets a fix, and a stale position naturally disappears
once the driver stops sending.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import uuid

    from lpg.infrastructure.redis.client import RedisClient

# A ping every ~15s with room for a couple of misses before the marker is
# considered stale on the client.
_TTL_SECONDS = 120


def _key(tenant_id: uuid.UUID, route_id: uuid.UUID) -> str:
    return f"tenant:{tenant_id}:route:{route_id}:driver_pos"


class RedisDriverLocationStore:
    def __init__(self, client: RedisClient) -> None:
        self._client = client

    async def save(
        self, tenant_id: uuid.UUID, route_id: uuid.UUID, snapshot: dict[str, Any]
    ) -> None:
        await self._client.client.setex(
            _key(tenant_id, route_id), _TTL_SECONDS, json.dumps(snapshot)
        )

    async def read(
        self, tenant_id: uuid.UUID, route_id: uuid.UUID
    ) -> dict[str, Any] | None:
        raw = await self._client.client.get(_key(tenant_id, route_id))
        if raw is None:
            return None
        try:
            parsed = json.loads(raw)
        except (ValueError, TypeError):
            return None
        return parsed if isinstance(parsed, dict) else None
