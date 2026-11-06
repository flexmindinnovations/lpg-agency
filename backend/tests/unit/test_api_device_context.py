"""Reading a phone's identity off a request, and the realtime connection's
device check (ADR-071)."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from starlette.requests import Request

from lpg.api.v1.dependencies.device import device_context_from, install_id_from
from lpg.api.v1.routers import ws
from lpg.api.v1.schemas.identity import DeviceInfoRequest
from lpg.application.common.errors import DeviceBlockedError, DeviceRequiredError

_GOOD_ID = "0123456789abcdef0123456789abcdef"


def _request(headers: dict[str, str]) -> Request:
    scope = {
        "type": "http",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
    }
    return Request(scope)


@pytest.mark.parametrize(
    "value", ["", "short", "has spaces in it 0123456789", "x" * 200, "a/b" * 10]
)
def test_a_malformed_install_id_counts_as_not_sent(value: str) -> None:
    assert install_id_from(_request({"X-Device-Id": value})) is None


def test_a_well_formed_install_id_is_read() -> None:
    assert install_id_from(_request({"X-Device-Id": f" {_GOOD_ID} "})) == _GOOD_ID


def test_no_phone_headers_and_no_body_means_the_web_dashboard() -> None:
    assert device_context_from(_request({}), None) is None


def test_only_known_app_types_are_honoured() -> None:
    admin = device_context_from(_request({"X-App-Type": "admin_app"}), None)
    odd = device_context_from(_request({"X-App-Type": "root_app", "X-Device-Id": _GOOD_ID}), None)

    assert admin is not None
    assert admin.app_type == "admin_app"
    assert odd is not None
    assert odd.app_type is None


def test_the_phones_details_come_from_the_body() -> None:
    info = DeviceInfoRequest(
        name="Ravi's phone", manufacturer="Xiaomi", model="Redmi 12", hardware_id="abc"
    )

    context = device_context_from(_request({"X-Device-Id": _GOOD_ID}), info)

    assert context is not None
    assert context.install_id == _GOOD_ID
    assert context.name == "Ravi's phone"
    assert context.details.model == "Redmi 12"
    assert context.hardware_id == "abc"


class _Gate:
    def __init__(self, error: Exception | None) -> None:
        self.error = error
        self.seen: dict[str, Any] = {}

    async def check(self, **kwargs: Any) -> None:
        self.seen = kwargs
        if self.error:
            raise self.error


def _claims(**extra: Any) -> dict[str, Any]:
    return {"tenant_id": str(uuid.uuid4()), "role": "driver", "sub": str(uuid.uuid4()), **extra}


async def test_the_realtime_connection_is_allowed_when_the_gate_is_satisfied(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gate = _Gate(None)
    monkeypatch.setattr(ws, "get_device_access_gate", lambda: gate)
    did = str(uuid.uuid4())

    assert await ws._device_allowed(_claims(did=did), _GOOD_ID) is None

    assert gate.seen["install_id"] == _GOOD_ID
    assert str(gate.seen["device_id"]) == did


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (DeviceBlockedError("blocked"), "DEVICE_BLOCKED"),
        (DeviceRequiredError("who?"), "DEVICE_REQUIRED"),
    ],
)
async def test_the_realtime_connection_is_closed_with_the_reason_code(
    monkeypatch: pytest.MonkeyPatch, error: Exception, code: str
) -> None:
    monkeypatch.setattr(ws, "get_device_access_gate", lambda: _Gate(error))

    assert await ws._device_allowed(_claims(did=str(uuid.uuid4())), _GOOD_ID) == code


async def test_a_token_with_no_tenant_is_not_device_checked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ws, "get_device_access_gate", lambda: _Gate(DeviceBlockedError("no")))

    assert await ws._device_allowed({"role": "super_admin", "tenant_id": None}, None) is None
