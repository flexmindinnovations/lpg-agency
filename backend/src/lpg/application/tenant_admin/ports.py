"""Tenant Admin repository ports."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    import uuid
    from collections.abc import Sequence

    from lpg.domain.tenant_admin.employee import Employee


@runtime_checkable
class EmployeeRepository(Protocol):
    def next_id(self) -> uuid.UUID: ...

    async def next_employee_code(self, tenant_id: uuid.UUID) -> str: ...

    async def get_by_id(self, employee_id: uuid.UUID) -> Employee | None: ...

    async def get_by_employee_code(self, employee_code: str) -> Employee | None: ...

    async def save(self, employee: Employee) -> None: ...

    async def list_employees(
        self,
        skip: int = 0,
        limit: int = 50,
        search: str | None = None,
        status: str | None = None,
        role: str | None = None,
        branch_id: uuid.UUID | None = None,
    ) -> Sequence[Employee]: ...

    async def count_employees(
        self,
        search: str | None = None,
        status: str | None = None,
        role: str | None = None,
        branch_id: uuid.UUID | None = None,
    ) -> int: ...


@dataclass(frozen=True, slots=True)
class DriverLoginResult:
    """What `DriverLoginProvisioner.enable` did, so a repeat call is visible as a no-op."""

    user_id: uuid.UUID
    driver_id: uuid.UUID
    #: `False` when the phone number already had a driver login that was adopted.
    login_created: bool
    #: `False` when the employee already had a driver profile that was linked.
    driver_created: bool


@runtime_checkable
class DriverLoginProvisioner(Protocol):
    """Gives a driver employee the phone login the Driver App signs in with.

    A login is only created when an employee is registered, so employees that
    pre-date that (seeded or imported) had none and OTP sign-in failed with "No
    account is associated with this number". Idempotent: a driver that already
    has a login linked to its profile is left untouched.
    """

    async def enable(self, tenant_id: uuid.UUID, employee: Employee) -> DriverLoginResult:
        """Create (or adopt) the driver login for `employee`'s phone number and
        link it to the employee's driver profile, creating the profile with a
        `PENDING` licence if there is none — in one transaction.

        Raises `ConflictError` when the phone number's login is deactivated,
        belongs to a non-driver role, or is already linked to a different driver.
        """
        ...
