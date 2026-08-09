"""``IdempotencyService``, against real Redis.

The four scenarios the Phase 2 instructions name explicitly: first request,
repeated request, conflicting payload, concurrent request.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import TYPE_CHECKING

import pytest

from lpg.application.common.errors import IdempotencyConflictError
from lpg.infrastructure.idempotency.service import IdempotencyService, fingerprint
from lpg.infrastructure.redis.client import RedisClient

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from lpg.config.settings import Settings

pytestmark = pytest.mark.integration


@pytest.fixture
async def service(
    integration_settings: Settings, redis_available: bool
) -> AsyncIterator[IdempotencyService]:
    if not redis_available:
        pytest.skip("Redis is not reachable — start it with ./scripts/dev-up.sh")
    client = RedisClient(integration_settings)
    client.connect()
    try:
        yield IdempotencyService(client)
    finally:
        await client.disconnect()


class TestFingerprint:
    def test_identical_payloads_fingerprint_identically(self) -> None:
        assert fingerprint({"a": 1, "b": 2}) == fingerprint({"b": 2, "a": 1})

    def test_different_payloads_fingerprint_differently(self) -> None:
        assert fingerprint({"a": 1}) != fingerprint({"a": 2})


class TestFirstRequest:
    async def test_executes_the_operation_and_returns_its_result(
        self, service: IdempotencyService
    ) -> None:
        tenant_id = uuid.uuid4()
        calls = 0

        async def operation() -> dict[str, int]:
            nonlocal calls
            calls += 1
            return {"order_id": 42}

        result = await service.execute(
            tenant_id=tenant_id,
            idempotency_key="key-1",
            request_fingerprint=fingerprint({"amount": 100}),
            operation=operation,
        )

        assert result == {"order_id": 42}
        assert calls == 1


class TestRepeatedRequest:
    async def test_replays_the_stored_result_without_re_executing(
        self, service: IdempotencyService
    ) -> None:
        tenant_id = uuid.uuid4()
        calls = 0
        fp = fingerprint({"amount": 100})

        async def operation() -> dict[str, int]:
            nonlocal calls
            calls += 1
            return {"order_id": 42, "attempt": calls}

        first = await service.execute(
            tenant_id=tenant_id,
            idempotency_key="key-2",
            request_fingerprint=fp,
            operation=operation,
        )
        second = await service.execute(
            tenant_id=tenant_id,
            idempotency_key="key-2",
            request_fingerprint=fp,
            operation=operation,
        )

        assert first == second == {"order_id": 42, "attempt": 1}
        assert calls == 1  # the second call never ran `operation` again

    async def test_different_tenants_never_share_a_key(self, service: IdempotencyService) -> None:
        tenant_a = uuid.uuid4()
        tenant_b = uuid.uuid4()
        fp = fingerprint({"amount": 100})

        async def operation_a() -> str:
            return "tenant-a-result"

        async def operation_b() -> str:
            return "tenant-b-result"

        result_a = await service.execute(
            tenant_id=tenant_a,
            idempotency_key="shared-key",
            request_fingerprint=fp,
            operation=operation_a,
        )
        result_b = await service.execute(
            tenant_id=tenant_b,
            idempotency_key="shared-key",
            request_fingerprint=fp,
            operation=operation_b,
        )

        assert result_a == "tenant-a-result"
        assert result_b == "tenant-b-result"


class TestConflictingPayload:
    async def test_raises_when_the_same_key_is_reused_with_a_different_fingerprint(
        self, service: IdempotencyService
    ) -> None:
        tenant_id = uuid.uuid4()

        async def operation() -> str:
            return "first-result"

        await service.execute(
            tenant_id=tenant_id,
            idempotency_key="key-3",
            request_fingerprint=fingerprint({"amount": 100}),
            operation=operation,
        )

        with pytest.raises(IdempotencyConflictError):
            await service.execute(
                tenant_id=tenant_id,
                idempotency_key="key-3",
                request_fingerprint=fingerprint({"amount": 999}),
                operation=operation,
            )

    async def test_a_failed_first_attempt_releases_the_key_for_retry(
        self, service: IdempotencyService
    ) -> None:
        """A failure must not permanently wedge the key — the client's next
        retry (same fingerprint) should be free to actually execute."""
        tenant_id = uuid.uuid4()
        fp = fingerprint({"amount": 100})

        async def failing_operation() -> str:
            msg = "simulated failure"
            raise RuntimeError(msg)

        with pytest.raises(RuntimeError, match="simulated failure"):
            await service.execute(
                tenant_id=tenant_id,
                idempotency_key="key-4",
                request_fingerprint=fp,
                operation=failing_operation,
            )

        async def succeeding_operation() -> str:
            return "succeeded-on-retry"

        result = await service.execute(
            tenant_id=tenant_id,
            idempotency_key="key-4",
            request_fingerprint=fp,
            operation=succeeding_operation,
        )
        assert result == "succeeded-on-retry"


class TestConcurrentRequest:
    async def test_concurrent_identical_requests_execute_the_operation_once(
        self, service: IdempotencyService
    ) -> None:
        tenant_id = uuid.uuid4()
        fp = fingerprint({"amount": 100})
        calls = 0

        async def slow_operation() -> dict[str, int]:
            nonlocal calls
            calls += 1
            await asyncio.sleep(0.3)
            return {"order_id": 7}

        results = await asyncio.gather(
            *(
                service.execute(
                    tenant_id=tenant_id,
                    idempotency_key="key-5",
                    request_fingerprint=fp,
                    operation=slow_operation,
                )
                for _ in range(5)
            )
        )

        assert calls == 1
        assert all(result == {"order_id": 7} for result in results)
