"""Structured logging, and specifically that redaction actually works.

The redaction test matters more than it looks. Redaction is implemented as a
pipeline processor precisely so it does not depend on every developer
remembering not to log a token at every call site — and a central mechanism
that silently stops working is worse than no mechanism, because everyone has
stopped watching for the problem it was meant to solve.
"""

from __future__ import annotations

import json
from io import StringIO
from typing import TYPE_CHECKING

import pytest
import structlog

from lpg.config.logging import configure_logging, get_logger

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture
def captured_logs() -> Iterator[StringIO]:
    """Capture structlog JSON output into a buffer."""
    buffer = StringIO()
    configure_logging(level="DEBUG", json_output=True)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            __import__("lpg.config.logging", fromlist=["_redact_sensitive"])._redact_sensitive,
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.PrintLoggerFactory(file=buffer),
        cache_logger_on_first_use=False,
    )
    yield buffer
    structlog.reset_defaults()


class TestStructuredOutput:
    def test_emits_valid_json(self, captured_logs: StringIO) -> None:
        get_logger("test").info("something_happened", order_count=3)

        payload = json.loads(captured_logs.getvalue().strip())
        assert payload["event"] == "something_happened"
        assert payload["order_count"] == 3
        assert "timestamp" in payload


class TestRedaction:
    @pytest.mark.parametrize(
        "field_name",
        [
            "password",
            "user_password",
            "passwordHash",
            "secret",
            "client_secret",
            "token",
            "access_token",
            "refresh_token",
            "authorization",
            "api_key",
            "apikey",
            "otp",
            "otp_code",
            "credential",
            "private_key",
            "session_id",
            "cookie",
        ],
    )
    def test_sensitive_fields_are_redacted(self, captured_logs: StringIO, field_name: str) -> None:
        get_logger("test").info("login_attempt", **{field_name: "super-secret-value"})

        output = captured_logs.getvalue()
        assert "super-secret-value" not in output
        assert "[REDACTED]" in output

    def test_non_sensitive_fields_pass_through(self, captured_logs: StringIO) -> None:
        get_logger("test").info(
            "order_created", order_id="abc-123", quantity=2, customer_name="Acme Ltd"
        )

        payload = json.loads(captured_logs.getvalue().strip())
        assert payload["order_id"] == "abc-123"
        assert payload["quantity"] == 2
        assert payload["customer_name"] == "Acme Ltd"

    def test_matching_is_case_insensitive_and_substring_based(
        self, captured_logs: StringIO
    ) -> None:
        """Catches naming variants without enumerating every one of them."""
        get_logger("test").info("event", UserPassword="x", MY_API_KEY="y")

        output = captured_logs.getvalue()
        assert "x" not in json.loads(output)["UserPassword"]
        assert json.loads(output)["MY_API_KEY"] == "[REDACTED]"
