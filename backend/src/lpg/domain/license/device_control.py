"""How strictly an agency controls which phones may use its Driver and Admin
apps (ADR-071). One per-agency setting, `device_control`, stored with the
rest of the tenant configuration.

    off      (default) nothing is enforced and nothing is recorded — a
             deploy changes nothing for an existing agency.
    observe  phones register themselves and show up in Linked Devices (as
             approved while seats remain); nobody is blocked. Used to build
             the list before enforcing.
    enforce  an unknown or waiting phone cannot use the app, and a blocked
             one is signed out.

The setting is a safety net against lock-outs, so anything unreadable falls
back to `off`, never to `enforce`.
"""

from __future__ import annotations

from enum import StrEnum

#: Tenant-configuration key holding the mode.
DEVICE_CONTROL_CONFIG_KEY = "device_control"

#: App types that go through approval. The Customer app is deliberately left
#: out: many households install freely and sign in with an OTP, so approving
#: their phones would add friction with no safety gain.
CONTROLLED_APP_TYPES = frozenset({"driver_app", "admin_app"})


class DeviceControlMode(StrEnum):
    OFF = "off"
    OBSERVE = "observe"
    ENFORCE = "enforce"

    @classmethod
    def parse(cls, value: object) -> DeviceControlMode:
        """Lenient read: a missing or unknown value means `off`."""
        if isinstance(value, str):
            try:
                return cls(value.strip().lower())
            except ValueError:
                return cls.OFF
        return cls.OFF

    @classmethod
    def is_valid(cls, value: object) -> bool:
        return isinstance(value, str) and value.strip().lower() in {m.value for m in cls}

    @property
    def records_devices(self) -> bool:
        return self is not DeviceControlMode.OFF

    @property
    def enforces(self) -> bool:
        return self is DeviceControlMode.ENFORCE
