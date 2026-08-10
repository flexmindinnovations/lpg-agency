"""Pydantic request/response models for `api/v1/routers/auth.py`.

First content in this previously-empty package — Phase 6 is the first
router this codebase mounts under `settings.api_v1_prefix`.
"""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class OtpRequestRequest(BaseModel):
    tenant_id: str
    phone_number: str


class OtpVerifyRequest(BaseModel):
    tenant_id: str
    phone_number: str
    code: str


class RefreshRequest(BaseModel):
    """`refresh_token` is optional in the body — the Dashboard's browser
    client relies on the `HttpOnly` cookie instead
    (`api/v1/routers/auth.py`'s module docstring). Mobile clients, which
    can't rely on a cookie, supply it here.
    """

    refresh_token: str | None = None


class LogoutRequest(BaseModel):
    refresh_token: str | None = None


class PasswordForgotRequest(BaseModel):
    email: EmailStr


class PasswordResetRequest(BaseModel):
    reset_token: str
    # Matches `Settings.password_min_length`'s NIST-style default (12) —
    # the floor this shape-validation layer enforces. An operator raising
    # the configured minimum beyond this would need a stricter check at the
    # use-case level too, since a Pydantic field constraint is fixed at
    # import time, not read from a per-request Settings instance.
    new_password: str = Field(min_length=12)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"  # noqa: S105 - the RFC 6750 scheme name, not a secret
    # Only populated for clients that can't rely on the HttpOnly cookie
    # (mobile) — the Dashboard reads the cookie instead, never this field.
    refresh_token: str | None = None


class PrincipalResponse(BaseModel):
    """Returned by `GET /auth/me` — feeds the Dashboard's permission-driven
    UI (`08-security-architecture.md` §3: the same permission list drives
    what renders client-side, while the API remains the actual enforcement
    point regardless).
    """

    user_id: str
    tenant_id: str | None
    role: str
    permissions: list[str]
