"""Contract test: an invalid WebSocket token closes with code 1008.

The historical bug this guards against — closing *before* `accept()`,
which collapses the code a **real browser** reports to the generic 1006
(abnormal closure) instead of 1008 — is a WHATWG `WebSocket` client
behaviour, not part of the ASGI close-message protocol Starlette's
`TestClient` exercises here. This test cannot see that distinction (it
passes identically whether `accept()` runs before the `close()` or not);
it was confirmed directly against a real browser instead: unpatched, the
handshake reported `code: 1006`; patched, `code: 1008`. This test's job is
to keep guarding the intended close code itself.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

if TYPE_CHECKING:
    from fastapi import FastAPI


def test_an_invalid_token_is_accepted_then_closed_with_1008(app: FastAPI) -> None:
    """The client only ever sees 1008 for a bad token if the handshake it
    rides on actually completed — asserting the close code is itself proof
    `accept()` ran first."""
    with (
        TestClient(app) as client,
        pytest.raises(WebSocketDisconnect) as exc_info,
        client.websocket_connect("/api/v1/ws?token=not-a-real-token") as websocket,
    ):
        websocket.receive_text()

    assert exc_info.value.code == 1008
