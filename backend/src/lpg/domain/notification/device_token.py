"""Device token — a push-notification delivery target.

Not an aggregate root: it has no invariants or lifecycle beyond "exists /
doesn't exist", and no domain events fire on register/unregister. A plain
value record the notification send path reads and the register endpoint
upserts.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

_VALID_PLATFORMS = frozenset({"android", "ios", "web"})


@dataclass(frozen=True, slots=True)
class DeviceToken:
    tenant_id: uuid.UUID
    recipient_user_id: uuid.UUID
    token: str
    platform: str
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_seen_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if self.platform not in _VALID_PLATFORMS:
            msg = f"Unknown device platform: {self.platform!r}"
            raise ValueError(msg)
        if not self.token.strip():
            msg = "Device token must not be empty."
            raise ValueError(msg)
