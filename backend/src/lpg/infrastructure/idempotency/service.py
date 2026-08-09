"""Idempotency-Key infrastructure.

``Idempotency-Key`` → request fingerprint → stored result → replay, per the
Phase 2 instructions. Tenant-aware by construction: the Redis key always
includes the tenant, so one tenant can never collide with — or replay —
another tenant's stored result, the same convention ``CacheClient`` already
follows.

No HTTP-layer wiring exists yet (no middleware, no dependency reading the
``Idempotency-Key`` header) — that arrives with the first mutating endpoint
that needs it. This is the storage/coordination primitive underneath it.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from typing import TYPE_CHECKING, Any

from lpg.application.common.errors import IdempotencyConflictError, ServiceUnavailableError
from lpg.config.logging import get_logger

if TYPE_CHECKING:
    import uuid
    from collections.abc import Awaitable, Callable

    from lpg.infrastructure.redis.client import RedisClient

_logger = get_logger(__name__)

# The window a request is considered "in progress" — long enough for a real
# use case to complete, short enough that a crashed request doesn't wedge the
# key forever. A completed result's own TTL (set separately, on completion)
# is what actually governs how long a key stays replayable.
_IN_PROGRESS_TTL_SECONDS = 30
_RESULT_TTL_SECONDS = 24 * 60 * 60
_POLL_INTERVAL_SECONDS = 0.1


def fingerprint(payload: dict[str, Any]) -> str:
    """A stable fingerprint for a request body, order-independent.

    ``json.dumps(..., sort_keys=True)`` before hashing so semantically
    identical payloads with differently-ordered keys fingerprint the same —
    a client re-serializing its own retry should never look like a conflict.
    """
    canonical = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class IdempotencyService:
    """Coordinates idempotent execution over Redis."""

    def __init__(self, client: RedisClient) -> None:
        self._client = client

    def _key(self, tenant_id: uuid.UUID, idempotency_key: str) -> str:
        return f"tenant:{tenant_id}:idempotency:{idempotency_key}"

    async def execute(
        self,
        *,
        tenant_id: uuid.UUID,
        idempotency_key: str,
        request_fingerprint: str,
        operation: Callable[[], Awaitable[Any]],
    ) -> Any:
        """Run ``operation`` at most once for this key; replay otherwise.

        - **First request**: claims the key, runs ``operation``, stores and
          returns the result.
        - **Repeated request, same fingerprint**: returns the stored result
          without re-running ``operation`` — even a completed one.
        - **Repeated request, different fingerprint**: raises
          ``IdempotencyConflictError`` — never silently executes a different
          request under a key a client already used.
        - **Concurrent request, still in progress**: polls briefly for the
          first request to finish, then replays its result — "concurrent
          identical requests serialize to one execution", not two.
        """
        key = self._key(tenant_id, idempotency_key)
        redis = self._client.client

        claimed = await redis.set(
            key,
            json.dumps({"status": "in_progress", "fingerprint": request_fingerprint}),
            nx=True,
            ex=_IN_PROGRESS_TTL_SECONDS,
        )

        if claimed:
            try:
                result = await operation()
            except Exception:
                # A failed attempt must not block a genuine retry — release
                # the claim rather than leaving it to expire.
                await redis.delete(key)
                raise
            await redis.set(
                key,
                json.dumps(
                    {"status": "completed", "fingerprint": request_fingerprint, "result": result}
                ),
                ex=_RESULT_TTL_SECONDS,
            )
            return result

        return await self._await_existing(key, request_fingerprint)

    async def _await_existing(self, key: str, request_fingerprint: str) -> Any:
        redis = self._client.client
        deadline = time.monotonic() + _IN_PROGRESS_TTL_SECONDS

        while True:
            raw = await redis.get(key)
            if raw is None:
                # The claim expired or was released (e.g. the first attempt
                # failed) between our SET NX and this read — nothing to
                # replay, and the key is free again. Not this call's job to
                # retry; the caller decides whether to retry `execute()`.
                msg = "Idempotency key is no longer in progress and has no stored result."
                raise ServiceUnavailableError(msg, idempotency_key=key)

            state = json.loads(raw)
            if state["fingerprint"] != request_fingerprint:
                msg = "This Idempotency-Key was already used with a different request."
                raise IdempotencyConflictError(msg, idempotency_key=key)

            if state["status"] == "completed":
                return state["result"]

            if time.monotonic() >= deadline:
                _logger.warning("idempotency_wait_timed_out", key=key)
                msg = "Timed out waiting for the original request to complete."
                raise ServiceUnavailableError(msg, idempotency_key=key)

            await asyncio.sleep(_POLL_INTERVAL_SECONDS)
