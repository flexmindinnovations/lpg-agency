"""Security-event trail for sign-in flows, and the per-event log line the
dispatcher writes. In-memory fakes only: no database."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from lpg.application.audit import security_events as sec
from lpg.application.common.errors import (
    AccountLockedError,
    InvalidCredentialsError,
    OtpMismatchError,
    RefreshTokenInvalidError,
)
from lpg.application.identity.login import LoginCommand, LoginUseCase
from lpg.application.identity.logout import LogoutCommand, LogoutUseCase
from lpg.application.identity.otp_request import RequestOtpCommand, RequestOtpUseCase
from lpg.application.identity.otp_verify import VerifyOtpCommand, VerifyOtpUseCase
from lpg.application.identity.refresh_token import RefreshTokenCommand, RefreshTokenUseCase
from lpg.domain.identity.refresh_token import RefreshToken
from lpg.domain.identity.user import IdentityUser
from lpg.domain.license.license import LicenseLifecycleState
from lpg.domain.order.order import BookingCreated
from lpg.infrastructure.events import dispatcher as dispatcher_module
from lpg.infrastructure.events.dispatcher import DomainEventDispatcher


class _Recorder:
    def __init__(self) -> None:
        self.events: list[sec.SecurityEvent] = []

    async def record(self, event: sec.SecurityEvent) -> None:
        self.events.append(event)


class _Users:
    def __init__(self, user: IdentityUser | None) -> None:
        self.user = user

    async def get_by_email(self, email: str) -> IdentityUser | None:
        del email
        return self.user

    async def get_by_phone_number(self, tenant_id: uuid.UUID, phone: str) -> IdentityUser | None:
        del tenant_id, phone
        return self.user

    async def get(self, user_id: uuid.UUID) -> IdentityUser | None:
        return self.user if self.user and self.user.id == user_id else None

    async def save(self, user: IdentityUser) -> None:
        del user


class _Tokens:
    def __init__(self) -> None:
        self.by_hash: dict[str, RefreshToken] = {}

    async def get_by_token_hash(self, token_hash: str) -> RefreshToken | None:
        return self.by_hash.get(token_hash)

    async def save(self, token: RefreshToken) -> None:
        self.by_hash[token.token_hash] = token

    async def revoke_all_for_user(self, user_id: uuid.UUID) -> None:
        for token in self.by_hash.values():
            if token.user_id == user_id:
                token.revoke()


class _Permissions:
    async def get_permission_codes_for_user(self, user_id: uuid.UUID) -> frozenset[str]:
        del user_id
        return frozenset()


class _Hasher:
    def hash(self, raw: str) -> str:
        return f"h:{raw}"


class _Signer:
    def issue_access_token(self, claims: dict[str, object]) -> str:
        return f"access-for-{claims['sub']}"


class _Passwords:
    def __init__(self, *, ok: bool) -> None:
        self._ok = ok

    def verify(self, password: str, password_hash: str) -> bool:
        del password, password_hash
        return self._ok

    def needs_rehash(self, password_hash: str) -> bool:
        del password_hash
        return False


class _License:
    async def get_status(self, tenant_id: uuid.UUID) -> LicenseLifecycleState:
        del tenant_id
        return LicenseLifecycleState.ACTIVE


class _Tenant:
    async def get_status(self, tenant_id: uuid.UUID) -> str:
        del tenant_id
        return "active"


class _Otp:
    def __init__(self, *, matches: bool) -> None:
        self._matches = matches

    async def issue(self, key: str) -> str:
        del key
        return "123456"

    async def verify(self, key: str, code: str) -> bool:
        del key, code
        return self._matches


class _Delivery:
    async def send(self, phone: str, code: str) -> None:
        del phone, code


class _Provisioner:
    async def provision(self, tenant_id: uuid.UUID, phone: str) -> IdentityUser | None:
        del tenant_id, phone
        return None


def _user() -> IdentityUser:
    return IdentityUser(
        uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        branch_id=None,
        email="meena@example.com",
        phone_number="+919876543210",
        password_hash="argon2-hash",
        role="agency_admin",
    )


def _login(user: IdentityUser | None, recorder: _Recorder, *, password_ok: bool) -> LoginUseCase:
    return LoginUseCase(
        _Users(user),
        _Tokens(),  # type: ignore[arg-type]
        _Permissions(),  # type: ignore[arg-type]
        _Passwords(ok=password_ok),  # type: ignore[arg-type]
        _Hasher(),  # type: ignore[arg-type]
        _Signer(),  # type: ignore[arg-type]
        _License(),  # type: ignore[arg-type]
        _Tenant(),  # type: ignore[arg-type]
        lockout_threshold=5,
        lockout_duration=timedelta(minutes=15),
        refresh_token_ttl=timedelta(days=30),
        security_events=recorder,
    )


class TestMasking:
    def test_email_keeps_first_letter_and_domain(self) -> None:
        assert sec.mask_email("meena@example.com") == "m***@example.com"

    def test_phone_keeps_last_four_digits(self) -> None:
        assert sec.mask_phone("+919876543210") == "*********3210"

    def test_reason_of_snake_cases_the_error_name(self) -> None:
        assert sec.reason_of(RefreshTokenInvalidError("x")) == "refresh_token_invalid"


class TestLogin:
    async def test_success_is_recorded_with_tenant_and_user(self) -> None:
        user, recorder = _user(), _Recorder()

        await _login(user, recorder, password_ok=True).execute(
            LoginCommand(email="meena@example.com", password="secret-pw")
        )

        (event,) = recorder.events
        assert (event.action, event.outcome) == (sec.LOGIN, "success")
        assert event.tenant_id == user.tenant_id
        assert event.user_id == user.id
        assert event.subject == "m***@example.com"

    async def test_wrong_password_is_recorded_without_the_password(self) -> None:
        user, recorder = _user(), _Recorder()

        with pytest.raises(InvalidCredentialsError):
            await _login(user, recorder, password_ok=False).execute(
                LoginCommand(email="meena@example.com", password="hunter2-attempt")
            )

        (event,) = recorder.events
        assert (event.action, event.outcome, event.reason) == (
            sec.LOGIN_FAILED,
            "failure",
            "bad_password",
        )
        assert "hunter2" not in repr(event)

    async def test_unknown_email_is_recorded_without_a_tenant(self) -> None:
        recorder = _Recorder()

        with pytest.raises(InvalidCredentialsError):
            await _login(None, recorder, password_ok=True).execute(
                LoginCommand(email="nobody@example.com", password="x")
            )

        (event,) = recorder.events
        assert event.reason == "unknown_account"
        assert event.tenant_id is None
        assert event.subject == "n***@example.com"

    async def test_locked_account_is_recorded(self) -> None:
        user, recorder = _user(), _Recorder()
        for _ in range(5):
            user.record_failed_login(
                reason="bad_password", lockout_threshold=5, lockout_duration=timedelta(minutes=15)
            )

        with pytest.raises(AccountLockedError):
            await _login(user, recorder, password_ok=True).execute(
                LoginCommand(email="meena@example.com", password="x")
            )

        assert recorder.events[-1].reason == "account_locked"


class TestOtp:
    async def test_request_records_that_a_code_was_sent_not_the_code(self) -> None:
        recorder, tenant_id = _Recorder(), uuid.uuid4()

        await RequestOtpUseCase(_Otp(matches=True), _Delivery(), recorder).execute(  # type: ignore[arg-type]
            RequestOtpCommand(tenant_id=tenant_id, phone_number="+919876543210")
        )

        (event,) = recorder.events
        assert event.action == sec.OTP_REQUESTED
        assert event.subject == "*********3210"
        assert "123456" not in repr(event)

    async def test_wrong_code_is_recorded_as_a_failure(self) -> None:
        recorder, tenant_id = _Recorder(), uuid.uuid4()
        use_case = VerifyOtpUseCase(
            _Otp(matches=False),  # type: ignore[arg-type]
            _Users(_user()),
            _Tokens(),  # type: ignore[arg-type]
            _Permissions(),  # type: ignore[arg-type]
            _Hasher(),  # type: ignore[arg-type]
            _Signer(),  # type: ignore[arg-type]
            _License(),  # type: ignore[arg-type]
            _Tenant(),  # type: ignore[arg-type]
            customer_login_provisioner=_Provisioner(),
            refresh_token_ttl=timedelta(days=30),
            security_events=recorder,
        )

        with pytest.raises(OtpMismatchError):
            await use_case.execute(
                VerifyOtpCommand(tenant_id=tenant_id, phone_number="+919876543210", code="000000")
            )

        (event,) = recorder.events
        assert (event.action, event.reason) == (sec.OTP_FAILED, "otp_mismatch")
        assert "000000" not in repr(event)

    async def test_good_code_is_recorded_as_a_login(self) -> None:
        recorder, user = _Recorder(), _user()
        use_case = VerifyOtpUseCase(
            _Otp(matches=True),  # type: ignore[arg-type]
            _Users(user),
            _Tokens(),  # type: ignore[arg-type]
            _Permissions(),  # type: ignore[arg-type]
            _Hasher(),  # type: ignore[arg-type]
            _Signer(),  # type: ignore[arg-type]
            _License(),  # type: ignore[arg-type]
            _Tenant(),  # type: ignore[arg-type]
            customer_login_provisioner=_Provisioner(),
            refresh_token_ttl=timedelta(days=30),
            security_events=recorder,
        )

        await use_case.execute(
            VerifyOtpCommand(tenant_id=user.tenant_id, phone_number="+919876543210", code="1")  # type: ignore[arg-type]
        )

        (event,) = recorder.events
        assert (event.action, event.outcome, event.user_id) == (sec.OTP_LOGIN, "success", user.id)


def _stored_token(user: IdentityUser, tokens: _Tokens, *, rotated: bool = False) -> RefreshToken:
    now = datetime.now(UTC)
    token = RefreshToken(
        uuid.uuid4(),
        user_id=user.id,
        token_hash=_Hasher().hash("raw-1"),
        issued_at=now,
        expires_at=now + timedelta(days=30),
    )
    if rotated:
        token.rotate(uuid.uuid4())
        token._rotated_at = now - timedelta(hours=1)
    tokens.by_hash[token.token_hash] = token
    return token


def _refresh(user: IdentityUser, tokens: _Tokens, recorder: _Recorder) -> RefreshTokenUseCase:
    return RefreshTokenUseCase(
        tokens,  # type: ignore[arg-type]
        _Users(user),
        _Permissions(),  # type: ignore[arg-type]
        _Hasher(),  # type: ignore[arg-type]
        _Signer(),  # type: ignore[arg-type]
        _License(),  # type: ignore[arg-type]
        _Tenant(),  # type: ignore[arg-type]
        refresh_token_ttl=timedelta(days=30),
        reuse_grace=timedelta(seconds=60),
        security_events=recorder,
    )


class TestRefreshAndLogout:
    async def test_successful_refresh_is_logged_but_not_persisted(self) -> None:
        user, tokens, recorder = _user(), _Tokens(), _Recorder()
        _stored_token(user, tokens)

        await _refresh(user, tokens, recorder).execute(RefreshTokenCommand(refresh_token="raw-1"))

        (event,) = recorder.events
        assert event.action == sec.TOKEN_REFRESHED
        assert event.persist is False

    async def test_unknown_token_is_recorded_as_a_failed_refresh(self) -> None:
        user, tokens, recorder = _user(), _Tokens(), _Recorder()

        with pytest.raises(RefreshTokenInvalidError):
            await _refresh(user, tokens, recorder).execute(
                RefreshTokenCommand(refresh_token="nope")
            )

        (event,) = recorder.events
        assert (event.action, event.outcome) == (sec.REFRESH_FAILED, "failure")
        assert "nope" not in repr(event)

    async def test_reuse_of_a_rotated_token_is_recorded_once_as_theft(self) -> None:
        user, tokens, recorder = _user(), _Tokens(), _Recorder()
        _stored_token(user, tokens, rotated=True)

        with pytest.raises(RefreshTokenInvalidError):
            await _refresh(user, tokens, recorder).execute(
                RefreshTokenCommand(refresh_token="raw-1")
            )

        (event,) = recorder.events
        assert event.action == sec.REFRESH_REUSE_DETECTED
        assert event.user_id == user.id

    async def test_logout_is_recorded_for_a_known_session(self) -> None:
        user, tokens, recorder = _user(), _Tokens(), _Recorder()
        _stored_token(user, tokens)

        await LogoutUseCase(
            tokens,  # type: ignore[arg-type]
            _Hasher(),  # type: ignore[arg-type]
            security_events=recorder,
            user_lookup=_Users(user),
        ).execute(LogoutCommand(refresh_token="raw-1"))

        (event,) = recorder.events
        assert (event.action, event.user_id, event.tenant_id) == (
            sec.LOGOUT,
            user.id,
            user.tenant_id,
        )

    async def test_logout_with_an_unknown_token_records_nothing(self) -> None:
        recorder = _Recorder()

        await LogoutUseCase(
            _Tokens(),  # type: ignore[arg-type]
            _Hasher(),  # type: ignore[arg-type]
            security_events=recorder,
        ).execute(LogoutCommand(refresh_token="nope"))

        assert recorder.events == []


class TestDispatcherEventLog:
    async def test_every_dispatched_event_gets_one_structured_log_line(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        dispatcher = DomainEventDispatcher()
        order_id, tenant_id = uuid.uuid4(), uuid.uuid4()
        event = BookingCreated(
            order_id=order_id,
            tenant_id=tenant_id,
            customer_id=uuid.uuid4(),
            booking_source="customer_app",
            requested_date=datetime.now(UTC),
        )

        logs: list[dict[str, object]] = []

        class _Capture:
            def info(self, name: str, **fields: object) -> None:
                logs.append({"event": name, **fields})

        monkeypatch.setattr(dispatcher_module, "_logger", _Capture())

        await dispatcher.dispatch([event])

        (line,) = [entry for entry in logs if entry["event"] == "domain_event"]
        assert line["event_name"] == "BookingCreated"
        assert line["order_id"] == str(order_id)
        assert line["tenant_id"] == str(tenant_id)
        assert line["booking_source"] == "customer_app"
