"""`OtpService` implements `application/identity/ports.py::OtpStore`.

Redis-backed: generates a numeric code, stores a salted SHA-256 hash with a
TTL (`Settings.otp_ttl_seconds`), matching `IdempotencyService`'s Redis-usage
shape. Rate limiting for the *request* step is enforced one layer up, at the
API dependency chain, via the existing `RateLimiter` (its docstring already
names "OTP requests" as an intended call site) — this class's job is
generate/store/verify only.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from typing import TYPE_CHECKING

from lpg.application.common.errors import OtpExpiredError

if TYPE_CHECKING:
    from lpg.config.settings import Settings
    from lpg.infrastructure.redis.client import RedisClient


class OtpService:
    def __init__(self, client: RedisClient, settings: Settings) -> None:
        self._client = client
        self._length = settings.otp_length
        self._ttl_seconds = settings.otp_ttl_seconds

    @staticmethod
    def _hash(code: str) -> str:
        return hashlib.sha256(code.encode("utf-8")).hexdigest()

    async def issue(self, key: str) -> str:
        code = "".join(str(secrets.randbelow(10)) for _ in range(self._length))
        redis = self._client.client
        await redis.set(key, self._hash(code), ex=self._ttl_seconds)
        return code

    async def verify(self, key: str, code: str) -> bool:
        redis = self._client.client
        stored_hash = await redis.get(key)
        if stored_hash is None:
            msg = "The OTP has expired."
            raise OtpExpiredError(msg)

        if hmac.compare_digest(self._hash(code), stored_hash):
            # Single-use: consume on a correct match. A wrong code leaves
            # the entry in place so the caller can retry within the same
            # TTL window.
            await redis.delete(key)
            return True
        return False
