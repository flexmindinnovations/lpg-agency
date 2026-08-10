"""`OtpService`, against real Redis."""

from __future__ import annotations

import os
import uuid
from typing import TYPE_CHECKING

import pytest

from lpg.application.common.errors import OtpExpiredError
from lpg.config.settings import Settings
from lpg.infrastructure.identity.otp_service import OtpService
from lpg.infrastructure.redis.client import RedisClient

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

pytestmark = pytest.mark.integration


@pytest.fixture
async def otp_service(redis_available: bool) -> AsyncIterator[OtpService]:
    if not redis_available:
        pytest.skip("Redis is not reachable — start it with ./scripts/dev-up.sh")
    settings = Settings(
        environment="local",
        redis_url=os.environ.get("LPG_TEST_REDIS_URL", "redis://localhost:56379/1"),
        otp_length=6,
        otp_ttl_seconds=300,
    )
    client = RedisClient(settings)
    client.connect()
    try:
        yield OtpService(client, settings)
    finally:
        await client.disconnect()


def _key() -> str:
    return f"test:otp:{uuid.uuid4()}"


class TestIssueAndVerify:
    async def test_issued_code_is_the_configured_length_and_all_digits(
        self, otp_service: OtpService
    ) -> None:
        code = await otp_service.issue(_key())

        assert len(code) == 6
        assert code.isdigit()

    async def test_verify_succeeds_for_the_correct_code(self, otp_service: OtpService) -> None:
        key = _key()
        code = await otp_service.issue(key)

        assert await otp_service.verify(key, code)

    async def test_verify_fails_for_the_wrong_code(self, otp_service: OtpService) -> None:
        key = _key()
        await otp_service.issue(key)

        assert not await otp_service.verify(key, "000000")

    async def test_a_correct_verify_consumes_the_code_single_use(
        self, otp_service: OtpService
    ) -> None:
        key = _key()
        code = await otp_service.issue(key)
        assert await otp_service.verify(key, code)

        with pytest.raises(OtpExpiredError):
            await otp_service.verify(key, code)

    async def test_a_wrong_verify_does_not_consume_the_code(self, otp_service: OtpService) -> None:
        key = _key()
        code = await otp_service.issue(key)

        assert not await otp_service.verify(key, "000000")
        # The real code still works — a mistyped attempt shouldn't burn it.
        assert await otp_service.verify(key, code)

    async def test_verify_raises_when_no_code_was_ever_issued(
        self, otp_service: OtpService
    ) -> None:
        with pytest.raises(OtpExpiredError):
            await otp_service.verify(_key(), "123456")

    async def test_reissuing_replaces_the_previous_code(self, otp_service: OtpService) -> None:
        key = _key()
        await otp_service.issue(key)
        second_code = await otp_service.issue(key)

        # The second `issue()` overwrote the stored value — only the latest
        # code verifies.
        assert await otp_service.verify(key, second_code)
