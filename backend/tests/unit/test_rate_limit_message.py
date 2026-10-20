"""CA-03: a rate-limited caller sees a friendly message with a wait time,
never the internal key (which can hold an IP address or phone number)."""

from __future__ import annotations

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from lpg.api.middleware.problem_details import register_exception_handlers
from lpg.application.common.errors import RateLimitExceededError
from lpg.infrastructure.rate_limit.limiter import too_many_attempts_message


def test_the_message_rounds_up_to_whole_minutes() -> None:
    assert too_many_attempts_message(30) == "Too many attempts. Please try again in 1 minute."
    assert too_many_attempts_message(1800) == "Too many attempts. Please try again in 30 minutes."


async def test_the_response_has_retry_after_and_no_key() -> None:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/limited")
    async def _limited() -> None:
        raise RateLimitExceededError(
            too_many_attempts_message(600),
            retry_after_seconds=600,
            key="auth:otp_request:203.0.113.9",
        )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        response = await client.get("/limited")
    assert response.status_code == 429
    assert response.headers["retry-after"] == "600"
    assert response.json()["retry_after_seconds"] == 600
    assert "203.0.113.9" not in response.text
    assert "auth:" not in response.text
