from __future__ import annotations

import uuid

import pytest

from lpg.application.common.errors import InvalidCredentialsError
from lpg.application.identity.otp_request import otp_store_key
from lpg.application.identity.role_otp_request import (
    RequestRoleOtpCommand,
    RequestRoleOtpUseCase,
)
from lpg.domain.identity.user import IdentityUser

TENANT_ID = uuid.uuid4()
PHONE = "+919999900099"


class FakeUserRepository:
    def __init__(self, user: IdentityUser | None) -> None:
        self.user = user
        self.looked_up: tuple[uuid.UUID, str] | None = None

    async def get_by_phone_number(self, tenant_id: uuid.UUID, phone: str) -> IdentityUser | None:
        self.looked_up = (tenant_id, phone)
        return self.user


class FakeOtpStore:
    def __init__(self) -> None:
        self.keys: list[str] = []

    async def issue(self, key: str) -> str:
        self.keys.append(key)
        return "123456"


class FakeOtpDelivery:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    async def send(self, phone_number: str, code: str) -> None:
        self.sent.append((phone_number, code))


def _user(**overrides: object) -> IdentityUser:
    defaults: dict[str, object] = {
        "tenant_id": TENANT_ID,
        "branch_id": None,
        "email": None,
        "phone_number": PHONE,
        "password_hash": None,
        "role": "driver",
    }
    defaults.update(overrides)
    return IdentityUser(uuid.uuid4(), **defaults)  # type: ignore[arg-type]


def _use_case(
    user: IdentityUser | None,
) -> tuple[RequestRoleOtpUseCase, FakeOtpStore, FakeOtpDelivery]:
    store = FakeOtpStore()
    delivery = FakeOtpDelivery()
    use_case = RequestRoleOtpUseCase(
        FakeUserRepository(user),  # type: ignore[arg-type]
        store,  # type: ignore[arg-type]
        delivery,  # type: ignore[arg-type]
    )
    return use_case, store, delivery


_COMMAND = RequestRoleOtpCommand(tenant_id=TENANT_ID, phone_number=PHONE, role="driver")


async def test_active_driver_gets_an_otp_issued_and_delivered() -> None:
    use_case, store, delivery = _use_case(_user())

    code = await use_case.execute(_COMMAND)

    assert code == "123456"
    assert store.keys == [otp_store_key(TENANT_ID, PHONE)]
    assert delivery.sent == [(PHONE, "123456")]


@pytest.mark.parametrize(
    "user",
    [None, _user(role="customer"), _user(role="agency_admin"), _user(is_active=False)],
)
async def test_unknown_other_role_or_inactive_number_is_rejected(
    user: IdentityUser | None,
) -> None:
    use_case, store, delivery = _use_case(user)

    with pytest.raises(InvalidCredentialsError):
        await use_case.execute(_COMMAND)

    assert store.keys == []
    assert delivery.sent == []


async def test_the_same_use_case_serves_customers() -> None:
    use_case, store, delivery = _use_case(_user(role="customer"))

    code = await use_case.execute(
        RequestRoleOtpCommand(tenant_id=TENANT_ID, phone_number=PHONE, role="customer")
    )

    assert code == "123456"
    assert delivery.sent == [(PHONE, "123456")]
    assert store.keys == [otp_store_key(TENANT_ID, PHONE)]
