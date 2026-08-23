"""`LinkedDevice` — one client app instance (Customer/Driver/Warehouse app)
registered against a tenant's license. Dashboard is deliberately excluded:
`app_type` only accepts `license.RECOGNIZED_APP_TYPES`, and Dashboard isn't
in that set — it's a browser session under the existing JWT model, not a
distinct installed app instance.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from lpg.domain.common.base import AggregateRoot, InvariantViolation
from lpg.domain.license.license import RECOGNIZED_APP_TYPES

if TYPE_CHECKING:
    import uuid
    from datetime import datetime


class LinkedDevice(AggregateRoot):
    __slots__ = (
        "_app_type",
        "_device_identifier",
        "_display_name",
        "_last_seen_at",
        "_license_id",
        "_registered_at",
        "_revoked_at",
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
        last_seen_at: datetime | None = None,
        revoked_at: datetime | None = None,
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
        self._display_name = display_name
        self._registered_at = registered_at
        self._last_seen_at = last_seen_at or registered_at
        self._revoked_at = revoked_at

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
    def revoked_at(self) -> datetime | None:
        return self._revoked_at

    @property
    def is_active(self) -> bool:
        return self._revoked_at is None

    def revoke(self, *, at: datetime) -> None:
        if self._revoked_at is not None:
            msg = "This device has already been revoked."
            raise InvariantViolation(msg, device_id=str(self.id))
        self._revoked_at = at

    def touch_last_seen(self, *, at: datetime) -> None:
        self._last_seen_at = at
