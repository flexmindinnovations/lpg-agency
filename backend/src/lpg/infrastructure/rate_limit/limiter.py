"""Rate-limiting foundation — a reusable Redis fixed-window counter.

Not wired to any endpoint with production-grade limits yet: this is the
primitive future call sites (login, OTP requests, password reset, public
APIs — `08-security-architecture.md` §"Rate Limiting") will build on, per
the Phase 2 instruction to establish the infrastructure without prematurely
adding aggressive limits that would interfere with development.

Fixed-window counter (``INCR`` + ``EXPIRE`` on first increment), not a
sliding-window log: simpler, one Redis round-trip per check, and the
boundary-burst imprecision fixed windows are known for is an acceptable
trade at foundation stage — revisit with a sliding-window or token-bucket
Lua script if a specific limit's precision requirement demands it later.

Tenant-aware by construction: callers key by ``tenant:{tenant_id}:...``,
matching ``CacheClient``'s and the idempotency service's convention, so a
limit is never accidentally shared or bypassed across a tenant boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from lpg.application.common.errors import RateLimitExceededError

if TYPE_CHECKING:
    from lpg.infrastructure.redis.client import RedisClient


@dataclass(frozen=True, slots=True)
class RateLimitResult:
    allowed: bool
    remaining: int
    retry_after_seconds: int


class RateLimiter:
    """A reusable fixed-window rate-limit check over Redis."""

    def __init__(self, client: RedisClient) -> None:
        self._client = client

    async def check(self, *, key: str, limit: int, window_seconds: int) -> RateLimitResult:
        """Increment the counter for ``key`` and report whether it's within
        ``limit`` for the current ``window_seconds`` window.

        ``INCR`` on a Redis key is atomic, so exactly one caller ever
        observes a freshly-created key's count as ``1`` — that caller alone
        sets the expiry, with no race window between the increment and the
        expiry taking effect.
        """
        redis = self._client.client
        count = await redis.incr(key)
        if count == 1:
            await redis.expire(key, window_seconds)

        if count <= limit:
            return RateLimitResult(allowed=True, remaining=limit - count, retry_after_seconds=0)

        ttl = await redis.ttl(key)
        return RateLimitResult(allowed=False, remaining=0, retry_after_seconds=max(ttl, 0))

    async def enforce(self, *, key: str, limit: int, window_seconds: int) -> RateLimitResult:
        """Like ``check()``, but raises ``RateLimitExceededError`` when over
        limit — the convenience form for a call site that just wants to
        fail closed rather than branch on the result itself."""
        result = await self.check(key=key, limit=limit, window_seconds=window_seconds)
        if not result.allowed:
            msg = f"Rate limit exceeded for {key!r}."
            raise RateLimitExceededError(
                msg, retry_after_seconds=result.retry_after_seconds, key=key
            )
        return result
