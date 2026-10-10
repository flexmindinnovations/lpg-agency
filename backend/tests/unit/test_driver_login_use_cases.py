"""Driver App two-step sign-in (password, then OTP) - behaviour and failure paths, no database."""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any

import pytest

from lpg.application.common.errors import (
    AccountLockedError,
    InvalidCredentialsError,
    LicenseNotActivatedError,
    OtpExpiredError,
    OtpMismatchError,
)
from lpg.application.identity.driver_login import (
    StartDriverLoginCommand,
    StartDriverLoginUseCase,
    VerifyDriverLoginCommand,
    VerifyDriverLoginUseCase,
    driver_login_otp_key,
    mask_phone_number,
)
from lpg.domain.identity.user import IdentityUser
from lpg.domain.license.license import LicenseLifecycleState

TENANT_ID = uuid.uuid4()
PASSWORD = "correct-horse-battery"
PHONE = "+919999900099"
EMAIL = "driver@example.com"


class _Hasher:
    def hash(self, password: str) -> str:
        return f"h:{password}"

    def verify(self, password: str, password_hash: str) -> bool:
        return password_hash == f"h:{password}"

    def needs_rehash(self, password_hash: str) -> bool:  # noqa: ARG002
        return False


class _Users:
    def __init__(self, *users: IdentityUser) -> None:
        self.by_email = {u.email: u for u in users}
        self.saved: list[IdentityUser] = []

    async def get_by_email(self, email: str) -> IdentityUser | None:
        return self.by_email.get(email)

    async def save(self, user: IdentityUser) -> None:
        self.saved.append(user)


class _Otp:
    def __init__(self) -> None:
        self.codes: dict[str, str] = {}

    async def issue(self, key: str) -> str:
        self.codes[key] = "123456"
        return "123456"

    async def verify(self, key: str, code: str) -> bool:
        if key not in self.codes:
            raise OtpExpiredError("expired")
        if self.codes[key] != code:
            return False
        del self.codes[key]
        return True


class _Delivery:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    async def send(self, phone_number: str, code: str) -> None:
        self.sent.append((phone_number, code))


class _Tenant:
    async def get_status(self, tenant_id: uuid.UUID) -> str:  # noqa: ARG002
        return "active"


class _License:
    def __init__(self, state: LicenseLifecycleState = LicenseLifecycleState.ACTIVE) -> None:
        self._state = state

    async def get_status(self, tenant_id: uuid.UUID) -> LicenseLifecycleState:  # noqa: ARG002
        return self._state


class _Refresh:
    def __init__(self) -> None:
        self.saved: list[Any] = []

    async def save(self, token: Any) -> None:
        self.saved.append(token)


class _Permissions:
    async def get_permission_codes_for_user(self, user_id: uuid.UUID) -> frozenset[str]:  # noqa: ARG002
        return frozenset({"orders:deliver"})


class _TokenHasher:
    def hash(self, token: str) -> str:
        return f"t:{token}"


class _Jwt:
    def issue_access_token(self, claims: dict[str, Any]) -> str:
        return f"jwt:{claims['sub']}:{claims['role']}"


def _driver(
    *,
    role: str = "driver",
    phone: str | None = PHONE,
    password_hash: str | None = f"h:{PASSWORD}",
    is_active: bool = True,
) -> IdentityUser:
    return IdentityUser(
        uuid.uuid4(),
        tenant_id=TENANT_ID,
        branch_id=None,
        email=EMAIL,
        phone_number=phone,
        password_hash=password_hash,
        role=role,
        is_active=is_active,
    )


def _start(
    users: _Users,
    otp: _Otp,
    delivery: _Delivery,
    license_state: LicenseLifecycleState | None = None,
) -> StartDriverLoginUseCase:
    return StartDriverLoginUseCase(
        users,
        _Hasher(),
        otp,
        delivery,
        _License(license_state or LicenseLifecycleState.ACTIVE),
        _Tenant(),
        lockout_threshold=3,
        lockout_duration=timedelta(minutes=15),
    )


def _verify(users: _Users, otp: _Otp, refresh: _Refresh) -> VerifyDriverLoginUseCase:
    return VerifyDriverLoginUseCase(
        users,
        otp,
        refresh,
        _Permissions(),
        _TokenHasher(),
        _Jwt(),
        _License(),
        _Tenant(),
        refresh_token_ttl=timedelta(days=30),
    )


async def test_correct_password_issues_otp_and_delivers_it() -> None:
    user = _driver()
    otp, delivery = _Otp(), _Delivery()

    challenge = await _start(_Users(user), otp, delivery).execute(
        StartDriverLoginCommand(email=EMAIL, password=PASSWORD)
    )

    assert challenge.code == "123456"
    assert challenge.phone_hint == "*********0099"
    assert PHONE not in challenge.phone_hint
    assert delivery.sent == [(PHONE, "123456")]
    assert driver_login_otp_key(TENANT_ID, user.id) in otp.codes


async def test_wrong_password_issues_no_otp_and_counts_a_failure() -> None:
    user = _driver()
    users, otp, delivery = _Users(user), _Otp(), _Delivery()

    with pytest.raises(InvalidCredentialsError):
        await _start(users, otp, delivery).execute(
            StartDriverLoginCommand(email=EMAIL, password="nope")
        )

    assert otp.codes == {}
    assert delivery.sent == []
    assert user.failed_login_count == 1
    assert users.saved == [user]


async def test_repeated_wrong_passwords_lock_the_account() -> None:
    user = _driver()
    use_case = _start(_Users(user), _Otp(), _Delivery())

    for _ in range(3):
        with pytest.raises(InvalidCredentialsError):
            await use_case.execute(StartDriverLoginCommand(email=EMAIL, password="nope"))

    with pytest.raises(AccountLockedError):
        await use_case.execute(StartDriverLoginCommand(email=EMAIL, password=PASSWORD))


@pytest.mark.parametrize(
    "user",
    [None, _driver(role="agency_admin"), _driver(password_hash=None), _driver(is_active=False)],
    ids=["unknown-email", "not-a-driver", "no-password", "inactive"],
)
async def test_non_driver_or_unusable_accounts_get_the_generic_error(
    user: IdentityUser | None,
) -> None:
    users = _Users(*([user] if user else []))
    otp = _Otp()

    with pytest.raises(InvalidCredentialsError, match="Email or password is incorrect"):
        await _start(users, otp, _Delivery()).execute(
            StartDriverLoginCommand(email=EMAIL, password=PASSWORD)
        )

    assert otp.codes == {}


async def test_driver_without_a_phone_number_cannot_start() -> None:
    with pytest.raises(InvalidCredentialsError, match="phone number"):
        await _start(_Users(_driver(phone=None)), _Otp(), _Delivery()).execute(
            StartDriverLoginCommand(email=EMAIL, password=PASSWORD)
        )


async def test_unactivated_licence_blocks_before_any_otp_is_issued() -> None:
    otp = _Otp()
    with pytest.raises(LicenseNotActivatedError):
        await _start(
            _Users(_driver()), otp, _Delivery(), LicenseLifecycleState.PENDING_ACTIVATION
        ).execute(StartDriverLoginCommand(email=EMAIL, password=PASSWORD))
    assert otp.codes == {}


async def test_correct_otp_after_password_returns_tokens() -> None:
    user = _driver()
    users, otp, refresh = _Users(user), _Otp(), _Refresh()
    await _start(users, otp, _Delivery()).execute(
        StartDriverLoginCommand(email=EMAIL, password=PASSWORD)
    )

    tokens = await _verify(users, otp, refresh).execute(
        VerifyDriverLoginCommand(email=EMAIL, code="123456")
    )

    assert tokens.access_token == f"jwt:{user.id}:driver"
    assert len(refresh.saved) == 1
    assert users.saved[-1] is user


async def test_wrong_otp_is_rejected_and_issues_no_tokens() -> None:
    users, otp, refresh = _Users(_driver()), _Otp(), _Refresh()
    await _start(users, otp, _Delivery()).execute(
        StartDriverLoginCommand(email=EMAIL, password=PASSWORD)
    )

    with pytest.raises(OtpMismatchError):
        await _verify(users, otp, refresh).execute(
            VerifyDriverLoginCommand(email=EMAIL, code="000000")
        )

    assert refresh.saved == []


async def test_otp_cannot_be_used_without_the_password_step() -> None:
    # No step 1 ran, so nothing is pending under the driver-login key.
    with pytest.raises(OtpExpiredError):
        await _verify(_Users(_driver()), _Otp(), _Refresh()).execute(
            VerifyDriverLoginCommand(email=EMAIL, code="123456")
        )


async def test_otp_is_single_use() -> None:
    users, otp = _Users(_driver()), _Otp()
    await _start(users, otp, _Delivery()).execute(
        StartDriverLoginCommand(email=EMAIL, password=PASSWORD)
    )
    verify = _verify(users, otp, _Refresh())
    await verify.execute(VerifyDriverLoginCommand(email=EMAIL, code="123456"))

    with pytest.raises(OtpExpiredError):
        await verify.execute(VerifyDriverLoginCommand(email=EMAIL, code="123456"))


async def test_verify_for_a_non_driver_is_the_generic_error() -> None:
    with pytest.raises(InvalidCredentialsError):
        await _verify(_Users(_driver(role="manager")), _Otp(), _Refresh()).execute(
            VerifyDriverLoginCommand(email=EMAIL, code="123456")
        )


def test_phone_mask_keeps_only_the_last_four_digits() -> None:
    assert mask_phone_number("+919999900099") == "*********0099"
    assert mask_phone_number("12") == "12"
