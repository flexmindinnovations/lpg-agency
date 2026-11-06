"""Device control enforcement rules (ADR-071): the sign-in binder and the
per-request gate, over the whole matrix of agency mode, who signs in and the
phone's state. In-memory fakes; the same rules are exercised against a real
database in `tests/integration/test_device_enforcement_api.py`."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from lpg.application.common.errors import (
    DeviceBlockedError,
    DevicePendingError,
    DeviceRemovedError,
    DeviceRequiredError,
)
from lpg.application.license.device_access import (
    DeviceAccess,
    DeviceAccessGate,
    DeviceBinding,
    DeviceContext,
    DeviceSessionBinder,
    controlled_app_type,
    fingerprint,
)
from lpg.application.license.manage_devices import DeviceRegistration, RegisterDeviceCommand
from lpg.domain.identity.user import IdentityUser
from lpg.domain.license.device_control import DeviceControlMode
from lpg.domain.license.linked_device import DeviceDetails, DeviceStatus, LinkedDevice

if TYPE_CHECKING:
    from lpg.application.common.errors import ApplicationError

_TENANT = uuid.uuid4()
_INSTALL = "install-id-0123456789abcdef"


class FakeModes:
    def __init__(self, mode: DeviceControlMode) -> None:
        self.mode = mode
        self.reads = 0

    async def get(self, _tenant_id: uuid.UUID) -> DeviceControlMode:
        self.reads += 1
        return self.mode

    async def invalidate(self, _tenant_id: uuid.UUID) -> None:
        return None


class FakeRegistrar:
    """Records what it was asked to register and answers with a device in the
    state the test set up."""

    def __init__(self, status: DeviceStatus = DeviceStatus.PENDING) -> None:
        self.status = status
        self.commands: list[RegisterDeviceCommand] = []
        self.device_id = uuid.uuid4()

    async def register(self, command: RegisterDeviceCommand) -> DeviceRegistration:
        self.commands.append(command)
        device = LinkedDevice(
            self.device_id,
            command.tenant_id,
            uuid.uuid4(),
            command.app_type,
            command.device_identifier,
            command.display_name,
            datetime.now(UTC),
            status=self.status,
            details=command.details,
        )
        return DeviceRegistration(device, is_new=False)


class FakeAccess:
    def __init__(self, access: DeviceAccess | None) -> None:
        self.access = access
        self.reads = 0

    async def get(self, _tenant_id: uuid.UUID, _device_id: uuid.UUID) -> DeviceAccess | None:
        self.reads += 1
        return self.access

    async def invalidate(self, _tenant_id: uuid.UUID, _device_id: uuid.UUID) -> None:
        return None


def _user(role: str = "driver", tenant_id: uuid.UUID | None = _TENANT) -> IdentityUser:
    return IdentityUser(
        uuid.uuid4(),
        tenant_id=tenant_id,
        branch_id=None,
        email="ops@example.com",
        phone_number="+919876543210",
        password_hash=None,
        role=role,
    )


def _context(app_type: str | None = None, install_id: str | None = _INSTALL) -> DeviceContext:
    return DeviceContext(
        install_id=install_id,
        app_type=app_type,
        name="Ravi's phone",
        details=DeviceDetails(model="Redmi 12"),
        hardware_id="android-id-1",
    )


def _access(status: DeviceStatus, install_id: str = _INSTALL) -> DeviceAccess:
    return DeviceAccess(
        device_id=uuid.uuid4(),
        app_type="driver_app",
        status=status,
        identifier_hash=fingerprint(install_id),
        display_name="Redmi 12",
    )


# -- Who is controlled ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("role", "declared", "expected"),
    [
        ("driver", None, "driver_app"),
        ("driver", "admin_app", "driver_app"),  # a driver cannot pose as anything else
        ("agency_admin", "admin_app", "admin_app"),
        ("manager", "admin_app", "admin_app"),
        ("agency_admin", None, None),  # the web dashboard
        ("agency_admin", "driver_app", None),
        ("customer", "admin_app", None),
        ("customer", None, None),
    ],
)
def test_who_is_under_device_control(role: str, declared: str | None, expected: str | None) -> None:
    assert controlled_app_type(role, declared) == expected


def test_the_install_id_is_hashed_and_stable() -> None:
    assert fingerprint(_INSTALL) == fingerprint(f"  {_INSTALL} ")
    assert _INSTALL not in fingerprint(_INSTALL)
    assert len(fingerprint(_INSTALL)) == 64


# -- Sign-in binder ------------------------------------------------------------------------


async def _bind(
    mode: DeviceControlMode,
    user: IdentityUser,
    context: DeviceContext | None,
    status: DeviceStatus = DeviceStatus.PENDING,
) -> tuple[DeviceBinding | None, FakeRegistrar]:
    registrar = FakeRegistrar(status)
    binder = DeviceSessionBinder(FakeModes(mode), registrar)
    return await binder.bind(user, context), registrar


async def test_off_records_nothing_and_binds_nothing() -> None:
    binding, registrar = await _bind(DeviceControlMode.OFF, _user(), _context())

    assert binding is None
    assert registrar.commands == []


@pytest.mark.parametrize("mode", [DeviceControlMode.OBSERVE, DeviceControlMode.ENFORCE])
async def test_a_driver_sign_in_is_recorded_with_only_hashed_identifiers(
    mode: DeviceControlMode,
) -> None:
    binding, registrar = await _bind(mode, _user(), _context())

    assert binding is not None
    assert binding.app_type == "driver_app"
    [command] = registrar.commands
    assert command.device_identifier == fingerprint(_INSTALL)
    assert command.hardware_ref == fingerprint("android-id-1")
    assert _INSTALL not in repr(command)
    assert "android-id-1" not in repr(command)
    assert command.display_name == "Ravi's phone"
    assert command.mode is mode


async def test_the_device_name_defaults_to_the_model() -> None:
    context = DeviceContext(install_id=_INSTALL, details=DeviceDetails(model="Redmi 12"))

    _, registrar = await _bind(DeviceControlMode.OBSERVE, _user(), context)

    assert registrar.commands[0].display_name == "Redmi 12"


@pytest.mark.parametrize("role", ["customer", "agency_admin"])
async def test_the_customer_app_and_the_web_dashboard_are_never_recorded(role: str) -> None:
    binding, registrar = await _bind(DeviceControlMode.ENFORCE, _user(role), _context())

    assert binding is None
    assert registrar.commands == []


async def test_the_admin_app_is_recorded_only_when_it_says_so() -> None:
    admin = _user("agency_admin")

    declared, registrar = await _bind(DeviceControlMode.ENFORCE, admin, _context("admin_app"))
    undeclared, other = await _bind(DeviceControlMode.ENFORCE, admin, _context(None))

    assert declared is not None
    assert declared.app_type == "admin_app"
    assert len(registrar.commands) == 1
    assert undeclared is None
    assert other.commands == []


async def test_a_super_admin_is_never_controlled() -> None:
    binding, registrar = await _bind(
        DeviceControlMode.ENFORCE, _user("super_admin", tenant_id=None), _context("admin_app")
    )

    assert binding is None
    assert registrar.commands == []


@pytest.mark.parametrize(
    "context", [None, DeviceContext(install_id=None), _context(install_id=" ")]
)
async def test_enforce_refuses_a_driver_that_does_not_identify_its_phone(
    context: DeviceContext | None,
) -> None:
    with pytest.raises(DeviceRequiredError):
        await _bind(DeviceControlMode.ENFORCE, _user(), context)


async def test_observe_lets_an_old_app_build_through_unrecorded() -> None:
    binding, registrar = await _bind(DeviceControlMode.OBSERVE, _user(), None)

    assert binding is None
    assert registrar.commands == []


@pytest.mark.parametrize(
    ("status", "error"),
    [(DeviceStatus.BLOCKED, DeviceBlockedError), (DeviceStatus.REMOVED, DeviceRemovedError)],
)
async def test_enforce_refuses_a_blocked_phone_at_sign_in(
    status: DeviceStatus, error: type[ApplicationError]
) -> None:
    with pytest.raises(error):
        await _bind(DeviceControlMode.ENFORCE, _user(), _context(), status)


async def test_a_waiting_phone_may_sign_in_so_it_can_ask_whether_it_is_approved() -> None:
    binding, _ = await _bind(DeviceControlMode.ENFORCE, _user(), _context(), DeviceStatus.PENDING)

    assert binding is not None


async def test_observe_never_blocks_even_a_blocked_phone() -> None:
    binding, _ = await _bind(DeviceControlMode.OBSERVE, _user(), _context(), DeviceStatus.BLOCKED)

    assert binding is not None


# -- Refresh --------------------------------------------------------------------------------


async def test_a_refresh_token_cannot_be_redeemed_from_another_phone_under_enforce() -> None:
    registrar = FakeRegistrar(DeviceStatus.APPROVED)
    binder = DeviceSessionBinder(FakeModes(DeviceControlMode.ENFORCE), registrar)

    with pytest.raises(DeviceRequiredError):
        await binder.rebind(_user(), _context(), uuid.uuid4())

    same = await binder.rebind(_user(), _context(), registrar.device_id)
    assert same is not None
    assert same.device_id == registrar.device_id


async def test_a_phone_bound_refresh_token_needs_the_phone_under_enforce_even_for_admin() -> None:
    binder = DeviceSessionBinder(FakeModes(DeviceControlMode.ENFORCE), FakeRegistrar())

    # An admin-app token redeemed with no headers must not quietly turn into
    # an unbound, dashboard-style session.
    with pytest.raises(DeviceRequiredError):
        await binder.rebind(_user("agency_admin"), None, uuid.uuid4())


async def test_a_refresh_after_control_is_switched_off_carries_on_unbound() -> None:
    binder = DeviceSessionBinder(FakeModes(DeviceControlMode.OFF), FakeRegistrar())

    assert await binder.rebind(_user(), _context(), uuid.uuid4()) is None


async def test_a_session_that_predates_control_is_bound_at_its_next_refresh() -> None:
    registrar = FakeRegistrar()
    binder = DeviceSessionBinder(FakeModes(DeviceControlMode.OBSERVE), registrar)

    binding = await binder.rebind(_user(), _context(), None)

    assert binding is not None
    assert len(registrar.commands) == 1


# -- Per-request gate -----------------------------------------------------------------------


def _gate(mode: DeviceControlMode, access: DeviceAccess | None) -> DeviceAccessGate:
    return DeviceAccessGate(FakeModes(mode), FakeAccess(access))


async def _check(
    gate: DeviceAccessGate,
    *,
    role: str = "driver",
    device_id: uuid.UUID | None = None,
    install_id: str | None = _INSTALL,
    enforce_status: bool = True,
) -> DeviceAccess | None:
    return await gate.check(
        tenant_id=_TENANT,
        role=role,
        device_id=device_id,
        install_id=install_id,
        enforce_status=enforce_status,
    )


@pytest.mark.parametrize("role", ["customer", "agency_admin", "manager", "super_admin"])
async def test_unbound_non_driver_sessions_cost_nothing_and_are_never_checked(role: str) -> None:
    modes = FakeModes(DeviceControlMode.ENFORCE)
    access = FakeAccess(None)
    gate = DeviceAccessGate(modes, access)

    assert await _check(gate, role=role) is None

    assert (modes.reads, access.reads) == (0, 0)


async def test_off_lets_everything_through_without_reading_the_phone() -> None:
    access = FakeAccess(_access(DeviceStatus.BLOCKED))
    gate = DeviceAccessGate(FakeModes(DeviceControlMode.OFF), access)

    assert await _check(gate, device_id=uuid.uuid4()) is None
    assert access.reads == 0


@pytest.mark.parametrize(
    ("status", "error"),
    [
        (DeviceStatus.PENDING, DevicePendingError),
        (DeviceStatus.BLOCKED, DeviceBlockedError),
        (DeviceStatus.REMOVED, DeviceRemovedError),
    ],
)
async def test_enforce_refuses_every_state_but_approved(
    status: DeviceStatus, error: type[ApplicationError]
) -> None:
    gate = _gate(DeviceControlMode.ENFORCE, _access(status))

    with pytest.raises(error):
        await _check(gate, device_id=uuid.uuid4())


async def test_enforce_lets_an_approved_phone_through() -> None:
    gate = _gate(DeviceControlMode.ENFORCE, _access(DeviceStatus.APPROVED))

    result = await _check(gate, device_id=uuid.uuid4())

    assert result is not None
    assert result.status is DeviceStatus.APPROVED


async def test_observe_never_refuses_a_blocked_phone() -> None:
    gate = _gate(DeviceControlMode.OBSERVE, _access(DeviceStatus.BLOCKED))

    result = await _check(gate, device_id=uuid.uuid4())

    assert result is not None


async def test_the_state_check_can_be_skipped_so_a_blocked_phone_can_learn_its_state() -> None:
    gate = _gate(DeviceControlMode.ENFORCE, _access(DeviceStatus.BLOCKED))

    result = await _check(gate, device_id=uuid.uuid4(), enforce_status=False)

    assert result is not None
    assert result.status is DeviceStatus.BLOCKED


@pytest.mark.parametrize("install_id", [None, "", "some-other-phone-0123456789"])
async def test_a_token_used_from_a_different_phone_is_refused_even_when_approved(
    install_id: str | None,
) -> None:
    gate = _gate(DeviceControlMode.ENFORCE, _access(DeviceStatus.APPROVED))

    with pytest.raises(DeviceRequiredError):
        await _check(gate, device_id=uuid.uuid4(), install_id=install_id)


async def test_the_different_phone_check_applies_even_to_the_state_free_endpoint() -> None:
    gate = _gate(DeviceControlMode.ENFORCE, _access(DeviceStatus.BLOCKED))

    with pytest.raises(DeviceRequiredError):
        await _check(
            gate,
            device_id=uuid.uuid4(),
            install_id="some-other-phone-0123456789",
            enforce_status=False,
        )


async def test_a_phone_that_no_longer_exists_is_refused_under_enforce() -> None:
    gate = _gate(DeviceControlMode.ENFORCE, None)

    with pytest.raises(DeviceRequiredError):
        await _check(gate, device_id=uuid.uuid4())


async def test_observe_does_not_refuse_a_mismatched_phone() -> None:
    gate = _gate(DeviceControlMode.OBSERVE, _access(DeviceStatus.APPROVED))

    await _check(gate, device_id=uuid.uuid4(), install_id="some-other-phone-0123456789")


async def test_a_driver_session_opened_before_control_must_bind_itself_under_enforce() -> None:
    with pytest.raises(DeviceRequiredError):
        await _check(_gate(DeviceControlMode.ENFORCE, None), device_id=None)

    assert await _check(_gate(DeviceControlMode.OBSERVE, None), device_id=None) is None
    assert await _check(_gate(DeviceControlMode.OFF, None), device_id=None) is None
