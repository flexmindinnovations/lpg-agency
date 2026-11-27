"""How strictly an agency controls which phones may use its Driver and Admin
apps (ADR-071). One per-agency setting, `device_control`, stored with the
rest of the tenant configuration.

    observe  (default) phones register themselves and show up in Linked
             Devices (as approved while seats remain); no phone needs approval,
             and one that cannot be recorded still signs in.
    enforce  an unknown or waiting phone cannot use the app.

A phone the admin blocks is refused in both modes.

The setting is a safety net against lock-outs, so anything unreadable falls
back to `observe`, never to `enforce`. That includes the old `off` value: a
list that stayed empty until somebody found a switch read as broken.
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
    OBSERVE = "observe"
    ENFORCE = "enforce"

    @classmethod
    def parse(cls, value: object) -> DeviceControlMode:
        """Lenient read: a missing or unknown value means `observe`."""
        if isinstance(value, str):
            try:
                return cls(value.strip().lower())
            except ValueError:
                return cls.OBSERVE
        return cls.OBSERVE

    @classmethod
    def is_valid(cls, value: object) -> bool:
        return isinstance(value, str) and value.strip().lower() in {m.value for m in cls}

    @property
    def enforces(self) -> bool:
        return self is DeviceControlMode.ENFORCE
