"""Fixtures scoped to `tests/integration/` only.

Kept separate from the top-level `tests/conftest.py` (whose fixtures also
serve unit tests that never touch a real Redis).
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


def _redis_url() -> str:
    # Mirrors `tests/conftest.py::_redis_url` — duplicated rather than
    # imported to keep this fixture self-contained and independent of
    # `tests` being importable as a package under any given pytest
    # invocation.
    return os.environ.get("LPG_TEST_REDIS_URL", "redis://localhost:56379/1")


@pytest.fixture(autouse=True)
async def _flush_auth_rate_limits(redis_available: bool) -> AsyncIterator[None]:
    """Clear `require_rate_limit`'s counters before every integration test.

    `auth:login`/`auth:otp_request`/`auth:password_forgot`
    (`dependencies/identity.py::require_rate_limit`) key by client IP, and
    every ASGI test client reports the same host — so login attempts from
    unrelated smoke tests accumulate against the *same* Redis key across the
    whole suite (all of `tests/integration/` shares one `lpg-redis`
    container, `tests/conftest.py::_redis_url`). Whichever test happens to
    run after ~10 prior logins then trips the 10/60s `auth:login` limit for
    a reason that has nothing to do with what it's testing — confirmed by
    every affected smoke test passing in isolation against a freshly
    flushed Redis.

    Scoped to the `auth:*` key namespace rather than the whole test DB, so
    it can't disturb OTP-store/idempotency/cache state another test set up
    (none of those use the `auth:` prefix — grep confirms `auth:` keys come
    only from `require_rate_limit`).
    """
    if redis_available:
        import redis.asyncio as redis

        # redis-py 5.x's `from_url` loses its type annotation under the <6
        # ceiling `arq` forces (ADR-029) — same note as `redis_available`.
        client = redis.from_url(_redis_url(), decode_responses=True)  # type: ignore[no-untyped-call]
        try:
            keys = [key async for key in client.scan_iter(match="auth:*")]
            if keys:
                await client.delete(*keys)
        finally:
            await client.aclose()
    yield
