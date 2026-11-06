"""`LinkedDevice` — one phone running a controlled app (Driver or Admin app)
registered against a tenant's licence, plus its approval state (ADR-071).

Dashboard and Customer app are deliberately not registered here: `app_type`
only accepts `license.RECOGNIZED_APP_TYPES`, and the Dashboard is a browser
session under the existing JWT model, not an installed app instance. The
Customer app is a recognised type (it can carry a seat limit) but is never
put through approval — see `lpg.application.license.device_access`.

**Identifiers are stored hashed.** `device_identifier` is the SHA-256 of the
random install ID the app keeps in secure storage, and `hardware_ref` is the
SHA-256 of the Android ID / iOS vendor ID. The plain values never reach the
database, the logs or the dashboard, so a leaked row cannot be replayed as a
device and the personal-data footprint stays minimal (DPDP). Admins tell
devices apart by the device name, model and a short reference taken from the
hash.

States and the only moves between them:

    pending  --approve-->  approved
    pending  --block---->  blocked
    approved --block---->  blocked
    blocked  --unblock-->  approved
    any but removed --remove--> removed
    removed  --(signs in again, via `reopen`)--> pending

`removed` frees the seat and is final until the phone asks again.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from lpg.domain.common.base import AggregateRoot, DomainEvent, InvariantViolation
from lpg.domain.license.license import RECOGNIZED_APP_TYPES

if TYPE_CHECKING:
    import uuid
    from datetime import datetime

#: Longest admin-typed note (IMEI, serial, asset tag). A note for the
#: agency's records, never a proof of identity.
MAX_ASSET_NOTE_LENGTH = 64
MAX_DISPLAY_NAME_LENGTH = 60


class DeviceStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    BLOCKED = "blocked"
    REMOVED = "removed"


@dataclass(frozen=True, slots=True)
class DeviceDetails:
    """What the app reports about its phone. All optional: an older build or
    a platform that hides a field simply leaves it empty."""

    manufacturer: str | None = None
    model: str | None = None
    os_version: str | None = None
    app_version: str | None = None
    platform: str | None = None


@dataclass(frozen=True, slots=True)
class DevicePendingApproval(DomainEvent):
    """A phone is waiting for an admin's decision — drives the admin alert."""

    device_id: uuid.UUID
    tenant_id: uuid.UUID
    app_type: str
    display_name: str


@dataclass(frozen=True, slots=True)
class DeviceStatusChanged(DomainEvent):
    """A device moved to a new state. Drives cache invalidation and tells a
    running app to re-check (realtime + push)."""

    device_id: uuid.UUID
    tenant_id: uuid.UUID
    app_type: str
    old_status: str
    new_status: str
    #: The person last signed in on the phone — who must be told.
    user_id: uuid.UUID | None
    display_name: str


def _clean(value: str | None, limit: int) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.split())
    return cleaned[:limit] or None


class LinkedDevice(AggregateRoot):
    __slots__ = (
        "_app_type",
        "_asset_note",
        "_details",
        "_device_identifier",
        "_display_name",
        "_hardware_ref",
        "_last_seen_at",
        "_last_user_id",
        "_last_user_name",
        "_license_id",
        "_registered_at",
        "_revoked_at",
        "_status",
        "_status_changed_at",
        "_status_changed_by",
        "_tenant_id",
    )

    def __init__(
        self,
        device_id: uuid.UUID,
        tenant_id: uuid.UUID,
        license_id: uuid.UUID,
        app_type: str,
        device_identifier: str,
        display_name: str,
        registered_at: datetime,
        *,
        status: DeviceStatus = DeviceStatus.PENDING,
        details: DeviceDetails | None = None,
        hardware_ref: str | None = None,
        asset_note: str | None = None,
        last_user_id: uuid.UUID | None = None,
        last_user_name: str | None = None,
        last_seen_at: datetime | None = None,
        revoked_at: datetime | None = None,
        status_changed_at: datetime | None = None,
        status_changed_by: uuid.UUID | None = None,
        version: int = 1,
    ) -> None:
        super().__init__(device_id, version=version)
        if app_type not in RECOGNIZED_APP_TYPES:
            msg = f"'{app_type}' is not a recognized app type."
            raise InvariantViolation(msg, app_type=app_type)

        self._tenant_id = tenant_id
        self._license_id = license_id
        self._app_type = app_type
        self._device_identifier = device_identifier
        self._display_name = _clean(display_name, MAX_DISPLAY_NAME_LENGTH) or "Unnamed phone"
        self._registered_at = registered_at
        self._status = status
        self._details = details or DeviceDetails()
        self._hardware_ref = hardware_ref
        self._asset_note = asset_note
        self._last_user_id = last_user_id
        self._last_user_name = last_user_name
        self._last_seen_at = last_seen_at or registered_at
        self._revoked_at = revoked_at
        self._status_changed_at = status_changed_at or registered_at
        self._status_changed_by = status_changed_by

    # -- Creation ---------------------------------------------------------------

    @classmethod
    def register(
        cls,
        device_id: uuid.UUID,
        tenant_id: uuid.UUID,
        license_id: uuid.UUID,
        app_type: str,
        device_identifier: str,
        display_name: str,
        *,
        at: datetime,
        status: DeviceStatus,
        details: DeviceDetails,
        hardware_ref: str | None,
        user_id: uuid.UUID | None,
        user_name: str | None,
    ) -> LinkedDevice:
        """A phone seen for the first time. `status` is decided by the caller
        (the agency's device-control mode and seat limit)."""
        if status not in (DeviceStatus.PENDING, DeviceStatus.APPROVED):
            msg = "A new device starts out pending or approved."
            raise InvariantViolation(msg, status=str(status))
        device = cls(
            device_id,
            tenant_id,
            license_id,
            app_type,
            device_identifier,
            display_name,
            at,
            status=status,
            details=details,
            hardware_ref=hardware_ref,
            last_user_id=user_id,
            last_user_name=user_name,
        )
        device._announce_if_pending()
        return device

    # -- Read -------------------------------------------------------------------

    @property
    def tenant_id(self) -> uuid.UUID:
        return self._tenant_id

    @property
    def license_id(self) -> uuid.UUID:
        return self._license_id

    @property
    def app_type(self) -> str:
        return self._app_type

    @property
    def device_identifier(self) -> str:
        return self._device_identifier

    @property
    def display_name(self) -> str:
        return self._display_name

    @property
    def registered_at(self) -> datetime:
        return self._registered_at

    @property
    def last_seen_at(self) -> datetime:
        return self._last_seen_at

    @property
    def status(self) -> DeviceStatus:
        return self._status

    @property
    def details(self) -> DeviceDetails:
        return self._details

    @property
    def hardware_ref(self) -> str | None:
        return self._hardware_ref

    @property
    def asset_note(self) -> str | None:
        return self._asset_note

    @property
    def last_user_id(self) -> uuid.UUID | None:
        return self._last_user_id

    @property
    def last_user_name(self) -> str | None:
        return self._last_user_name

    @property
    def revoked_at(self) -> datetime | None:
        """When the admin removed the device (`None` while it is in use)."""
        return self._revoked_at

    @property
    def status_changed_at(self) -> datetime:
        return self._status_changed_at

    @property
    def status_changed_by(self) -> uuid.UUID | None:
        return self._status_changed_by

    @property
    def is_active(self) -> bool:
        return self._status is not DeviceStatus.REMOVED

    @property
    def holds_seat(self) -> bool:
        """Only approved phones count against the plan's device limit."""
        return self._status is DeviceStatus.APPROVED

    # -- Admin decisions --------------------------------------------------------

    def approve(self, *, by: uuid.UUID | None, at: datetime) -> None:
        self._require(
            self._status is DeviceStatus.PENDING, "Only a waiting device can be approved."
        )
        self._move(DeviceStatus.APPROVED, by=by, at=at)

    def block(self, *, by: uuid.UUID | None, at: datetime) -> None:
        self._require(
            self._status in (DeviceStatus.PENDING, DeviceStatus.APPROVED),
            "Only a waiting or approved device can be blocked.",
        )
        self._move(DeviceStatus.BLOCKED, by=by, at=at)

    def unblock(self, *, by: uuid.UUID | None, at: datetime) -> None:
        self._require(
            self._status is DeviceStatus.BLOCKED, "Only a blocked device can be unblocked."
        )
        self._move(DeviceStatus.APPROVED, by=by, at=at)

    def remove(self, *, by: uuid.UUID | None, at: datetime) -> None:
        self._require(self._status is not DeviceStatus.REMOVED, "This device is already removed.")
        self._revoked_at = at
        self._move(DeviceStatus.REMOVED, by=by, at=at)

    def rename(self, display_name: str) -> None:
        cleaned = _clean(display_name, MAX_DISPLAY_NAME_LENGTH)
        if cleaned is None:
            msg = "A device needs a name."
            raise InvariantViolation(msg, device_id=str(self.id))
        self._display_name = cleaned

    def set_asset_note(self, note: str | None) -> None:
        cleaned = _clean(note, MAX_ASSET_NOTE_LENGTH + 1)
        if cleaned is not None and len(cleaned) > MAX_ASSET_NOTE_LENGTH:
            msg = f"The note can be at most {MAX_ASSET_NOTE_LENGTH} characters."
            raise InvariantViolation(msg, device_id=str(self.id))
        self._asset_note = cleaned

    # -- Seen on the phone ------------------------------------------------------

    def record_sign_in(
        self,
        *,
        at: datetime,
        user_id: uuid.UUID | None,
        user_name: str | None,
        details: DeviceDetails,
        hardware_ref: str | None,
    ) -> None:
        """The phone signed in: remember who, and refresh what it reports."""
        self._last_seen_at = at
        self._last_user_id = user_id
        self._last_user_name = user_name
        self._details = details
        self._hardware_ref = hardware_ref or self._hardware_ref

    def touch_last_seen(self, *, at: datetime) -> None:
        self._last_seen_at = at

    def reopen(self, *, status: DeviceStatus, at: datetime) -> None:
        """A removed phone asks again: it goes back through the same door as a
        new one, never straight back to approved."""
        self._require(
            self._status is DeviceStatus.REMOVED, "Only a removed device can be reopened."
        )
        self._require(
            status in (DeviceStatus.PENDING, DeviceStatus.APPROVED),
            "A reopened device starts out pending or approved.",
        )
        self._revoked_at = None
        self._move(status, by=None, at=at)
        self._announce_if_pending()

    # -- Internals --------------------------------------------------------------

    def _require(self, condition: bool, message: str) -> None:
        if not condition:
            raise InvariantViolation(message, device_id=str(self.id), status=str(self._status))

    def _move(self, new_status: DeviceStatus, *, by: uuid.UUID | None, at: datetime) -> None:
        old_status = self._status
        self._status = new_status
        self._status_changed_at = at
        self._status_changed_by = by
        self.record_event(
            DeviceStatusChanged(
                device_id=self.id,
                tenant_id=self._tenant_id,
                app_type=self._app_type,
                old_status=old_status.value,
                new_status=new_status.value,
                user_id=self._last_user_id,
                display_name=self._display_name,
            )
        )

    def _announce_if_pending(self) -> None:
        if self._status is DeviceStatus.PENDING:
            self.record_event(
                DevicePendingApproval(
                    device_id=self.id,
                    tenant_id=self._tenant_id,
                    app_type=self._app_type,
                    display_name=self._display_name,
                )
            )
