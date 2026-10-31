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

from lpg.application.common.errors import OtpExpiredError, RateLimitExceededError

#: Wrong codes tolerated per issued code. A 6-digit code has 10^6 values, so
#: unlimited guessing inside the TTL would break it; after this many misses the
#: code is destroyed and the caller must request a new one (OWASP ASVS 2.7.2).
MAX_VERIFY_ATTEMPTS = 5


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

    async def issue(self, key: str, *, ttl_seconds: int | None = None) -> str:
        code = "".join(str(secrets.randbelow(10)) for _ in range(self._length))
        redis = self._client.client
        await redis.set(key, self._hash(code), ex=ttl_seconds or self._ttl_seconds)
        await redis.delete(self._attempts_key(key))
        return code

    @staticmethod
    def _attempts_key(key: str) -> str:
        return f"{key}:attempts"

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
            await redis.delete(key, self._attempts_key(key))
            return True

        attempts_key = self._attempts_key(key)
        attempts = await redis.incr(attempts_key)
        if attempts == 1:
            ttl = await redis.ttl(key)
            await redis.expire(attempts_key, max(ttl, 1))
        if attempts >= MAX_VERIFY_ATTEMPTS:
            await redis.delete(key, attempts_key)
            msg = "Too many incorrect codes. Please request a new code."
            raise RateLimitExceededError(msg, retry_after_seconds=60)
        return False
