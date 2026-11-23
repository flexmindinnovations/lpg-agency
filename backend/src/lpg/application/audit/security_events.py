"""Security-event trail: who signed in, out, refreshed or reset a password.

The generic audit hook records *data changes* made inside a Unit of Work. Sign-in
traffic never goes through one (there is no tenant context yet when a login
starts, see `application/identity/login.py`), so these events are recorded
explicitly through this port.

Each event is written twice: as a structured log line (always, so a failure to
reach the database never hides a failed login) and as an `audit.audit_log` row
that the dashboard Audit Log page already lists. Never put a password, OTP,
token or hash in an event; the email or phone number is stored masked.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    import uuid

# Audit-log `action` values (the dashboard filters by these prefixes).
LOGIN = "auth.login"
LOGIN_FAILED = "auth.login_failed"
OTP_REQUESTED = "auth.otp_requested"
OTP_LOGIN = "auth.otp_login"
OTP_FAILED = "auth.otp_failed"
TOKEN_REFRESHED = "auth.token_refreshed"  # noqa: S105 - an action name, not a secret
REFRESH_FAILED = "auth.refresh_failed"
REFRESH_REUSE_DETECTED = "auth.refresh_reuse_detected"
LOGOUT = "auth.logout"
PASSWORD_RESET_REQUESTED = "auth.password_reset_requested"  # noqa: S105
PASSWORD_RESET = "auth.password_reset"  # noqa: S105

#: `audit_log.entity_name` for every event here.
ENTITY_NAME = "auth_session"


def mask_email(email: str) -> str:
    """`meena@example.com` -> `m***@example.com`."""
    local, sep, domain = email.partition("@")
    if not sep:
        return mask_phone(email)
    return f"{local[:1]}***@{domain}"


def mask_phone(phone: str) -> str:
    """`+919876543210` -> `*********3210` (keeps the last four digits)."""
    if len(phone) <= 4:
        return "*" * len(phone)
    return f"{'*' * (len(phone) - 4)}{phone[-4:]}"


def reason_of(exc: Exception) -> str:
    """`DeviceBlockedError` -> `device_blocked` (a short machine reason)."""
    name = type(exc).__name__.removesuffix("Error")
    return "".join(f"_{c.lower()}" if c.isupper() else c for c in name).lstrip("_")


@dataclass(frozen=True, slots=True)
class SecurityEvent:
    action: str
    #: "success" or "failure".
    outcome: str
    tenant_id: uuid.UUID | None = None
    user_id: uuid.UUID | None = None
    #: Masked email or phone the attempt was made with.
    subject: str | None = None
    #: Short machine reason on a failure (`bad_password`, `locked`, ...).
    reason: str | None = None
    extra: dict[str, object] = field(default_factory=dict)
    #: False for high-frequency events (token refresh) that belong in the logs
    #: only, so they don't bury sign-ins and failures in the audit table.
    persist: bool = True


@runtime_checkable
class SecurityEventRecorder(Protocol):
    async def record(self, event: SecurityEvent) -> None:
        """Best-effort: must never raise into the sign-in flow."""
        ...
