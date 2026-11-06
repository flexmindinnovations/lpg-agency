"""Device-control dependencies (ADR-071): reading the phone's identity off a
request, and building the sign-in binder and the per-request gate.

A Driver or Admin app sends `X-Device-Id` (its random install ID) and
`X-App-Type` on every request; sign-in, OTP verify and refresh also carry the
phone's details in the body. Anything malformed is treated as "not sent" — the
gate then decides what that means for the agency's mode.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from fastapi import Request

from lpg.application.license.device_access import (
    ADMIN_APP,
    DRIVER_APP,
    DeviceAccessGate,
    DeviceContext,
    DeviceSessionBinder,
)
from lpg.domain.license.linked_device import DeviceDetails

if TYPE_CHECKING:
    from lpg.api.v1.schemas.identity import DeviceInfoRequest
    from lpg.application.license.ports import DeviceControlModeReader

DEVICE_ID_HEADER = "X-Device-Id"
APP_TYPE_HEADER = "X-App-Type"

#: Install IDs are random tokens (UUID-like); anything else is not one.
_INSTALL_ID = re.compile(r"^[A-Za-z0-9._~-]{16,128}$")
_APP_TYPES = frozenset({ADMIN_APP, DRIVER_APP})


def install_id_from(request: Request) -> str | None:
    raw = request.headers.get(DEVICE_ID_HEADER, "").strip()
    return raw if _INSTALL_ID.fullmatch(raw) else None


def device_context_from(request: Request, info: DeviceInfoRequest | None) -> DeviceContext | None:
    """The phone behind a sign-in or refresh, or `None` when the request came
    from no Driver/Admin app at all (the web dashboard, the Customer app)."""
    install_id = install_id_from(request)
    declared = request.headers.get(APP_TYPE_HEADER, "").strip()
    app_type = declared if declared in _APP_TYPES else None
    if install_id is None and app_type is None and info is None:
        return None
    details = DeviceDetails()
    name = None
    hardware_id = None
    if info is not None:
        name = info.name
        hardware_id = info.hardware_id
        details = DeviceDetails(
            manufacturer=info.manufacturer,
            model=info.model,
            os_version=info.os_version,
            app_version=info.app_version,
            platform=info.platform,
        )
    return DeviceContext(
        install_id=install_id,
        app_type=app_type,
        name=name,
        details=details,
        hardware_id=hardware_id,
    )


def get_device_session_binder() -> DeviceSessionBinder:
    from lpg.api.app import get_app_state
    from lpg.infrastructure.license.device_access import (
        RedisDeviceControlModeReader,
        SqlAlchemyDeviceRegistrar,
    )
    from lpg.infrastructure.redis.cache import RedisCacheClient

    state = get_app_state()
    if state.redis is None or state.database is None:
        msg = "Redis/Database are not configured — the application lifespan has not run."
        raise RuntimeError(msg)
    modes = RedisDeviceControlModeReader(RedisCacheClient(state.redis), state.database)
    return DeviceSessionBinder(
        modes, SqlAlchemyDeviceRegistrar(state.database, state.event_dispatcher)
    )


def get_device_access_gate() -> DeviceAccessGate:
    from lpg.api.app import get_app_state
    from lpg.infrastructure.license.device_access import (
        RedisDeviceAccessReader,
        RedisDeviceControlModeReader,
    )
    from lpg.infrastructure.redis.cache import RedisCacheClient

    state = get_app_state()
    if state.redis is None or state.database is None:
        msg = "Redis/Database are not configured — the application lifespan has not run."
        raise RuntimeError(msg)
    cache = RedisCacheClient(state.redis)
    return DeviceAccessGate(
        RedisDeviceControlModeReader(cache, state.database),
        RedisDeviceAccessReader(cache, state.database),
    )


def get_device_control_mode_reader() -> DeviceControlModeReader:
    from lpg.api.app import get_app_state
    from lpg.infrastructure.license.device_access import RedisDeviceControlModeReader
    from lpg.infrastructure.redis.cache import RedisCacheClient

    state = get_app_state()
    if state.redis is None or state.database is None:
        msg = "Redis/Database are not configured — the application lifespan has not run."
        raise RuntimeError(msg)
    return RedisDeviceControlModeReader(RedisCacheClient(state.redis), state.database)
