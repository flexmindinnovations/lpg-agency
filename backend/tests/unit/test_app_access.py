"""Each mobile app admits only its own kind of account. In-memory fakes only."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import Request

from lpg.api.v1.dependencies.device import mobile_app_from
from lpg.application.audit import security_events as sec
from lpg.application.common.errors import (
    ApplicationError,
    InvalidCredentialsError,
    RefreshTokenInvalidError,
)
from lpg.application.identity.app_access import app_admits
from lpg.application.identity.login import LoginCommand, LoginUseCase
from lpg.application.identity.otp_verify import VerifyOtpCommand, VerifyOtpUseCase
from lpg.application.identity.refresh_token import RefreshTokenCommand, RefreshTokenUseCase
from lpg.domain.identity.refresh_token import RefreshToken
from lpg.domain.identity.user import IdentityUser
from tests.unit.test_security_events import (
    _Hasher,
    _License,
    _Otp,
    _Passwords,
    _Permissions,
    _Recorder,
    _Signer,
    _Tenant,
    _Tokens,
    _Users,
)

_PHONE = "+919876543210"


def _user(role: str) -> IdentityUser:
    return IdentityUser(
        uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        branch_id=None,
        email="someone@example.com",
        phone_number=_PHONE,
        password_hash="argon2-hash",
        role=role,
    )


class _NoCustomer:
    """No agency customer has the number."""

    async def provision(self, tenant_id: uuid.UUID, phone: str) -> IdentityUser | None:
        del tenant_id, phone
        return None


class _Provisioner:
    """Would create a customer login for the number."""

    def __init__(self) -> None:
        self.calls = 0

    async def provision(self, tenant_id: uuid.UUID, phone: str) -> IdentityUser:
        del tenant_id, phone
        self.calls += 1
        return _user("customer")


def _verify_otp(
    user: IdentityUser | None,
    recorder: _Recorder,
    tokens: _Tokens,
    provisioner: _Provisioner | _NoCustomer | None = None,
) -> VerifyOtpUseCase:
    return VerifyOtpUseCase(
        _Otp(matches=True),  # type: ignore[arg-type]
        _Users(user),
        tokens,  # type: ignore[arg-type]
        _Permissions(),  # type: ignore[arg-type]
        _Hasher(),  # type: ignore[arg-type]
        _Signer(),  # type: ignore[arg-type]
        _License(),  # type: ignore[arg-type]
        _Tenant(),  # type: ignore[arg-type]
        customer_login_provisioner=provisioner or _Provisioner(),
        refresh_token_ttl=timedelta(days=30),
        security_events=recorder,
    )


def _otp(app: str | None) -> VerifyOtpCommand:
    return VerifyOtpCommand(tenant_id=uuid.uuid4(), phone_number=_PHONE, code="123456", app=app)


_STAFF = ("agency_admin", "manager", "warehouse_staff", "dispatcher", "accountant")


@pytest.mark.parametrize(
    ("app", "admitted"),
    [
        ("customer_app", {"customer"}),
        ("driver_app", {"driver"}),
        ("admin_app", {*_STAFF, "super_admin"}),
        (None, {"customer", "driver", "super_admin", *_STAFF}),
    ],
)
def test_which_roles_each_app_admits(app: str | None, admitted: set[str]) -> None:
    for role in ("customer", "driver", "super_admin", *_STAFF):
        assert app_admits(app, role) is (role in admitted), (app, role)


def _seen_by_the_client(error: ApplicationError) -> tuple[str, int, str, str]:
    """Everything of a refusal that reaches the response."""
    return (error.error_code, error.http_status, error.title, error.message)


@pytest.mark.parametrize(("app", "role"), [("driver_app", "customer"), ("customer_app", "driver")])
async def test_otp_sign_in_to_the_wrong_app_looks_like_an_unknown_number(
    app: str, role: str
) -> None:
    recorder, tokens = _Recorder(), _Tokens()

    with pytest.raises(InvalidCredentialsError) as wrong_app:
        await _verify_otp(_user(role), recorder, tokens).execute(_otp(app))
    # The same app, with a number that has no account at all.
    with pytest.raises(InvalidCredentialsError) as unknown:
        await _verify_otp(None, _Recorder(), _Tokens(), _NoCustomer()).execute(_otp(app))

    assert _seen_by_the_client(wrong_app.value) == _seen_by_the_client(unknown.value)
    assert wrong_app.value.context == unknown.value.context
    assert role not in wrong_app.value.message.lower()
    assert tokens.by_hash == {}
    # Our own log still says why.
    (event,) = recorder.events
    assert (event.outcome, event.reason) == ("failure", "wrong_app")


@pytest.mark.parametrize(("app", "role"), [("driver_app", "driver"), ("customer_app", "customer")])
async def test_otp_sign_in_to_the_right_app_works(app: str, role: str) -> None:
    tokens = _Tokens()

    await _verify_otp(_user(role), _Recorder(), tokens).execute(_otp(app))

    assert len(tokens.by_hash) == 1


@pytest.mark.parametrize("app", ["driver_app", "admin_app"])
async def test_an_unknown_number_creates_no_customer_login_from_other_apps(app: str) -> None:
    provisioner = _Provisioner()

    with pytest.raises(InvalidCredentialsError):
        await _verify_otp(None, _Recorder(), _Tokens(), provisioner).execute(_otp(app))

    assert provisioner.calls == 0


@pytest.mark.parametrize("app", ["customer_app", None])
async def test_a_first_customer_sign_in_still_creates_the_login(app: str | None) -> None:
    provisioner = _Provisioner()

    await _verify_otp(None, _Recorder(), _Tokens(), provisioner).execute(_otp(app))

    assert provisioner.calls == 1


async def test_password_sign_in_to_the_wrong_app_looks_like_a_wrong_password() -> None:
    recorder, tokens = _Recorder(), _Tokens()
    use_case = LoginUseCase(
        _Users(_user("agency_admin")),
        tokens,  # type: ignore[arg-type]
        _Permissions(),  # type: ignore[arg-type]
        _Passwords(ok=True),  # type: ignore[arg-type]
        _Hasher(),  # type: ignore[arg-type]
        _Signer(),  # type: ignore[arg-type]
        _License(),  # type: ignore[arg-type]
        _Tenant(),  # type: ignore[arg-type]
        lockout_threshold=5,
        lockout_duration=timedelta(minutes=15),
        refresh_token_ttl=timedelta(days=30),
        security_events=recorder,
    )

    with pytest.raises(InvalidCredentialsError) as refused:
        await use_case.execute(
            LoginCommand(email="someone@example.com", password="pw", app="driver_app")
        )

    assert refused.value.message == "Email or password is incorrect."
    assert refused.value.context == {}

    assert tokens.by_hash == {}
    (event,) = recorder.events
    assert (event.action, event.reason) == (sec.LOGIN_FAILED, "wrong_app")


async def test_a_session_already_open_in_the_wrong_app_cannot_be_refreshed() -> None:
    user, tokens = _user("customer"), _Tokens()
    now = datetime.now(UTC)
    token = RefreshToken(
        uuid.uuid4(),
        user_id=user.id,
        token_hash=_Hasher().hash("raw-1"),
        issued_at=now,
        expires_at=now + timedelta(days=30),
    )
    tokens.by_hash[token.token_hash] = token
    use_case = RefreshTokenUseCase(
        tokens,  # type: ignore[arg-type]
        _Users(user),
        _Permissions(),  # type: ignore[arg-type]
        _Hasher(),  # type: ignore[arg-type]
        _Signer(),  # type: ignore[arg-type]
        _License(),  # type: ignore[arg-type]
        _Tenant(),  # type: ignore[arg-type]
        refresh_token_ttl=timedelta(days=30),
    )

    with pytest.raises(RefreshTokenInvalidError) as refused:
        await use_case.execute(RefreshTokenCommand(refresh_token="raw-1", app="driver_app"))
    with pytest.raises(RefreshTokenInvalidError) as dead:
        await use_case.execute(RefreshTokenCommand(refresh_token="never-issued"))

    assert _seen_by_the_client(refused.value) == _seen_by_the_client(dead.value)

    # Not rotated, and not treated as theft: the right app can still use it.
    assert token.rotated_at is None
    await use_case.execute(RefreshTokenCommand(refresh_token="raw-1", app="customer_app"))


@pytest.mark.parametrize(
    ("header", "app"),
    [
        ("customer_app", "customer_app"),
        (" driver_app ", "driver_app"),
        ("admin_app", "admin_app"),
        ("something_else", None),
        (None, None),
    ],
)
def test_the_app_is_read_from_its_header(header: str | None, app: str | None) -> None:
    headers = [] if header is None else [(b"x-app-type", header.encode())]

    assert mobile_app_from(Request({"type": "http", "headers": headers})) == app
