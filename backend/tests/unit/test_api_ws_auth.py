"""Contract tests for WebSocket authentication (DO-38 / CA-18).

The token travels in the first frame (`{"type": "auth", "token": ...}`),
never the URL, so it can't land in an access log. A missing, invalid or
late token closes with 1008 — after `accept()`, because a browser only
reports 1008 (and not a generic 1006) when the handshake completed.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from lpg.config.logging import QuerySecretRedactingFilter, redact_query_secrets

if TYPE_CHECKING:
    from fastapi import FastAPI


def test_an_invalid_auth_frame_is_closed_with_1008(app: FastAPI) -> None:
    with (
        TestClient(app) as client,
        pytest.raises(WebSocketDisconnect) as exc_info,
        client.websocket_connect("/api/v1/ws") as websocket,
    ):
        websocket.send_json({"type": "auth", "token": "not-a-real-token"})
        websocket.receive_text()

    assert exc_info.value.code == 1008


def test_a_first_frame_that_is_not_auth_is_closed_with_1008(app: FastAPI) -> None:
    with (
        TestClient(app) as client,
        pytest.raises(WebSocketDisconnect) as exc_info,
        client.websocket_connect("/api/v1/ws") as websocket,
    ):
        websocket.send_json({"subscribe": ["notifications"]})
        websocket.receive_text()

    assert exc_info.value.code == 1008


def test_the_legacy_query_token_is_still_verified(app: FastAPI) -> None:
    """Installed app builds still send `?token=` (transition period)."""
    with (
        TestClient(app) as client,
        pytest.raises(WebSocketDisconnect) as exc_info,
        client.websocket_connect("/api/v1/ws?token=not-a-real-token") as websocket,
    ):
        websocket.receive_text()

    assert exc_info.value.code == 1008


def test_access_log_lines_never_carry_a_token() -> None:
    line = '127.0.0.1:51850 - "WebSocket /api/v1/ws?token=eyJhbGciOiJSUzI1NiIs.x.y" [accepted]'
    assert redact_query_secrets(line) == (
        '127.0.0.1:51850 - "WebSocket /api/v1/ws?token=[REDACTED]" [accepted]'
    )
    assert redact_query_secrets("GET /x?page=2&access_token=abc HTTP/1.1") == (
        "GET /x?page=2&access_token=[REDACTED] HTTP/1.1"
    )

    # uvicorn logs the handshake as a %-format record with the path in args.
    record = logging.LogRecord(
        "uvicorn.error",
        logging.INFO,
        __file__,
        1,
        '%s - "WebSocket %s" %s',
        ("127.0.0.1:1", "/api/v1/ws?token=secret.jwt.value", "[accepted]"),
        None,
    )
    assert QuerySecretRedactingFilter().filter(record) is True
    assert "secret.jwt.value" not in record.getMessage()
    assert "token=[REDACTED]" in record.getMessage()
