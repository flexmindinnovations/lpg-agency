"""Enforcing device control (ADR-071): binding a session to a phone at sign-in
and refresh, and checking that phone on every request and realtime connection.

Two small services, both driven by the agency's `device_control` mode:

- `DeviceSessionBinder` runs when a Driver or Admin app user signs in or
  refreshes. It records the phone, refuses a blocked one, and returns the
  binding the tokens carry. Without `enforce`, a phone that cannot be recorded
  still signs in.
- `DeviceAccessGate` runs on every authenticated request. It checks the
  phone the token was issued to against the cached status.

A blocked phone is refused in both modes: the agency chose that phone. The
mode only decides whether a phone needs approval before it can be used.

Who is controlled: a *driver* login is always the Driver app (so it cannot
dodge the check by leaving headers out); a staff login is the Admin app only
when the app says so with `X-App-Type: admin_app`; staff on the web dashboard,
customers and super admins are never controlled.
"""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from lpg.application.common.errors import (
    DeviceBlockedError,
    DevicePendingError,
    DeviceRemovedError,
    DeviceRequiredError,
)
from lpg.application.license.manage_devices import RegisterDeviceCommand
from lpg.config.logging import get_logger
from lpg.domain.license.device_control import CONTROLLED_APP_TYPES, DeviceControlMode
from lpg.domain.license.linked_device import DeviceDetails, DeviceStatus

if TYPE_CHECKING:
    import uuid

    from lpg.application.license.ports import (
        DeviceAccessReader,
        DeviceControlModeReader,
        DeviceRegistrar,
    )
    from lpg.domain.identity.user import IdentityUser

_logger = get_logger(__name__)

DRIVER_ROLE = "driver"
_CUSTOMER_ROLE = "customer"
ADMIN_APP = "admin_app"
DRIVER_APP = "driver_app"


def fingerprint(value: str) -> str:
    """SHA-256 of an install ID or hardware ID. Both are high-entropy or
    low-value identifiers, so a fast hash is the right tool; the point is that
    the plain value is never stored or logged."""
    return hashlib.sha256(value.strip().encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class DeviceContext:
    """What the app told us about its phone, with the plain identifiers. It
    lives only for the duration of a request."""

    install_id: str | None
    app_type: str | None = None
    name: str | None = None
    details: DeviceDetails = field(default_factory=DeviceDetails)
    hardware_id: str | None = None


@dataclass(frozen=True, slots=True)
class DeviceBinding:
    """What a token carries so later requests can find the phone."""

    device_id: uuid.UUID
    app_type: str


@dataclass(frozen=True, slots=True)
class DeviceAccess:
    """The cached view of one phone that request checks need."""

    device_id: uuid.UUID
    app_type: str
    status: DeviceStatus
    #: SHA-256 of the install ID the phone registered with.
    identifier_hash: str
    display_name: str
    #: False while the name is the generated default and the app should ask once.
    name_confirmed: bool = True


def controlled_app_type(role: str, declared_app_type: str | None) -> str | None:
    """Which controlled app (if any) a login on this role belongs to."""
    if role == DRIVER_ROLE:
        return DRIVER_APP
    if role == _CUSTOMER_ROLE:
        return None
    if declared_app_type == ADMIN_APP:
        return ADMIN_APP
    return None


def raise_for_status(status: DeviceStatus) -> None:
    """The error a phone in this state gets under `enforce`."""
    if status is DeviceStatus.PENDING:
        msg = "This phone is waiting for your agency to approve it."
        raise DevicePendingError(msg)
    if status is DeviceStatus.BLOCKED:
        msg = "Your agency has blocked this phone. Please contact your agency."
        raise DeviceBlockedError(msg)
    if status is DeviceStatus.REMOVED:
        msg = "Your agency removed this phone from its list. Sign in again to ask for approval."
        raise DeviceRemovedError(msg)


def refuses(mode: DeviceControlMode, status: DeviceStatus) -> bool:
    """Whether the agency keeps a phone in this state out of the app."""
    if status is DeviceStatus.BLOCKED:
        return True
    return mode.enforces and status is not DeviceStatus.APPROVED


def _matches(install_id: str | None, identifier_hash: str) -> bool:
    return bool(install_id) and hmac.compare_digest(fingerprint(install_id or ""), identifier_hash)


class DeviceSessionBinder:
    def __init__(self, modes: DeviceControlModeReader, registrar: DeviceRegistrar) -> None:
        self._modes = modes
        self._registrar = registrar

    async def bind(self, user: IdentityUser, context: DeviceContext | None) -> DeviceBinding | None:
        """Record the phone and return its binding, or `None` when this login
        is not under device control. Raises for a blocked phone, and under
        `enforce` for one that cannot be identified or was removed."""
        tenant_id = user.tenant_id
        if tenant_id is None:  # super admin: above any one agency
            return None
        app_type = controlled_app_type(user.role, context.app_type if context else None)
        if app_type is None or app_type not in CONTROLLED_APP_TYPES:
            return None

        mode = await self._modes.get(tenant_id)
        if context is None or not (context.install_id or "").strip():
            if mode.enforces:
                msg = "This app did not identify its phone. Please update the app."
                raise DeviceRequiredError(msg)
            return None

        command = RegisterDeviceCommand(
            tenant_id=tenant_id,
            app_type=app_type,
            device_identifier=fingerprint(context.install_id or ""),
            display_name=context.name,
            details=context.details,
            hardware_ref=fingerprint(context.hardware_id) if context.hardware_id else None,
            user_id=user.id,
            user_name=user.display_name or user.email or user.phone_number,
            mode=mode,
        )
        try:
            registration = await self._registrar.register(command)
        except Exception as exc:
            if mode.enforces:
                raise
            # Only keeping a list: that must never keep somebody out.
            _logger.warning("device_record_failed", error_type=type(exc).__name__)
            return None
        device = registration.device
        # A waiting phone may sign in: that is how it learns it was approved.
        if device.status is not DeviceStatus.PENDING and refuses(mode, device.status):
            raise_for_status(device.status)
        return DeviceBinding(device.id, app_type)

    async def rebind(
        self, user: IdentityUser, context: DeviceContext | None, bound_device_id: uuid.UUID | None
    ) -> DeviceBinding | None:
        """`bind` for a refresh: a refresh token opened on a phone may only be
        redeemed from that same phone while the agency enforces control."""
        binding = await self.bind(user, context)
        if bound_device_id is None or user.tenant_id is None:
            return binding
        if binding is not None and binding.device_id == bound_device_id:
            return binding
        if (await self._modes.get(user.tenant_id)).enforces:
            msg = "This session was opened on a different phone."
            raise DeviceRequiredError(msg)
        # Control was switched down since sign-in: carry on with whatever the
        # phone now reports (possibly nothing).
        return binding


class DeviceAccessGate:
    def __init__(self, modes: DeviceControlModeReader, access: DeviceAccessReader) -> None:
        self._modes = modes
        self._access = access

    async def check(
        self,
        *,
        tenant_id: uuid.UUID,
        role: str,
        device_id: uuid.UUID | None,
        install_id: str | None,
        enforce_status: bool = True,
    ) -> DeviceAccess | None:
        """Check the phone behind one request.

        Returns the phone's cached access record (or `None` when the session
        is not under device control). Raises `DeviceRequiredError` (401) when
        the session is not tied to this phone and, when `enforce_status` is set,
        the blocked error (403) — plus pending and removed under `enforce`.
        `enforce_status=False` is for the one endpoint a waiting or blocked
        phone must still reach to learn its own state.
        """
        if device_id is None and role != DRIVER_ROLE:
            return None  # web dashboard, customer, super admin: no I/O at all

        mode = await self._modes.get(tenant_id)
        if device_id is None:
            # A driver session opened before control was switched on (or by an
            # old build). 401 so the app refreshes and binds itself.
            if mode.enforces:
                msg = "This session is not tied to a registered phone."
                raise DeviceRequiredError(msg)
            return None

        access = await self._access.get(tenant_id, device_id)
        if access is None or not _matches(install_id, access.identifier_hash):
            if mode.enforces:
                msg = "This session was opened on a different phone."
                raise DeviceRequiredError(msg)
            return access
        if enforce_status and refuses(mode, access.status):
            raise_for_status(access.status)
        return access

    async def forget(self, tenant_id: uuid.UUID, device_id: uuid.UUID) -> None:
        """Drop the cached record of one phone (its name just changed)."""
        await self._access.invalidate(tenant_id, device_id)

    async def mode(self, tenant_id: uuid.UUID) -> DeviceControlMode:
        return await self._modes.get(tenant_id)
