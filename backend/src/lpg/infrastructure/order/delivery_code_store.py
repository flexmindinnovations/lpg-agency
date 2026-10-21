"""`RedisDeliveryCodeStore` implements `application/order/ports.py::
DeliveryCodeStore`.

The plaintext delivery code lives next to `OtpService`'s salted hash, under
its own tenant- and order-scoped key, with the same TTL. It is only ever
read back for the order's own customer (`GetDeliveryCodeUseCase`); the
verification path still checks the hash, never this copy.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import uuid

    from lpg.infrastructure.redis.client import RedisClient


def _key(tenant_id: uuid.UUID, order_id: uuid.UUID) -> str:
    return f"tenant:{tenant_id}:order-delivery-code:{order_id}"


class RedisDeliveryCodeStore:
    def __init__(self, client: RedisClient) -> None:
        self._client = client

    async def remember(
        self, tenant_id: uuid.UUID, order_id: uuid.UUID, code: str, *, ttl_seconds: int
    ) -> None:
        await self._client.client.set(_key(tenant_id, order_id), code, ex=ttl_seconds)

    async def recall(self, tenant_id: uuid.UUID, order_id: uuid.UUID) -> str | None:
        code = await self._client.client.get(_key(tenant_id, order_id))
        return code if isinstance(code, str) else None
