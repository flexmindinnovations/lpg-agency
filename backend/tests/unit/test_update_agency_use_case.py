"""`UpdateAgencyDetailsUseCase` - no database."""

from __future__ import annotations

import uuid

import pytest

from lpg.application.common.errors import NotFoundError
from lpg.application.tenant.update_agency import (
    UpdateAgencyDetailsCommand,
    UpdateAgencyDetailsUseCase,
)
from lpg.domain.common.base import InvariantViolation
from lpg.domain.tenant.tenant import Tenant


class _FakeTenantRepository:
    def __init__(self, *tenants: Tenant) -> None:
        self._tenants = {tenant.id: tenant for tenant in tenants}
        self.saved: list[Tenant] = []

    async def get(self, tenant_id: uuid.UUID) -> Tenant | None:
        return self._tenants.get(tenant_id)

    async def save(self, tenant: Tenant) -> None:
        self.saved.append(tenant)


class _FakeUnitOfWork:
    def __init__(self) -> None:
        self.commits = 0

    async def commit(self) -> None:
        self.commits += 1


def _tenant(status: str = "active") -> Tenant:
    return Tenant(
        uuid.uuid4(),
        "Sunrise Gas Agency",
        "sunrise-gas",
        status=status,
        primary_contact_email="ops@sunrise-gas.example",
    )


def _use_case(
    repository: _FakeTenantRepository, unit_of_work: _FakeUnitOfWork
) -> UpdateAgencyDetailsUseCase:
    return UpdateAgencyDetailsUseCase(repository, unit_of_work)  # type: ignore[arg-type]


def _command(tenant_id: uuid.UUID) -> UpdateAgencyDetailsCommand:
    return UpdateAgencyDetailsCommand(
        tenant_id=tenant_id, name="Sunrise LPG", primary_contact_email="owner@sunrise.example"
    )


async def test_saves_the_new_details_in_one_commit() -> None:
    tenant = _tenant()
    repository = _FakeTenantRepository(tenant)
    unit_of_work = _FakeUnitOfWork()

    result = await _use_case(repository, unit_of_work).execute(_command(tenant.id))

    assert (result.name, result.primary_contact_email) == (
        "Sunrise LPG",
        "owner@sunrise.example",
    )
    assert repository.saved == [tenant]
    assert unit_of_work.commits == 1


async def test_an_unknown_agency_is_not_found() -> None:
    unit_of_work = _FakeUnitOfWork()

    with pytest.raises(NotFoundError):
        await _use_case(_FakeTenantRepository(), unit_of_work).execute(_command(uuid.uuid4()))

    assert unit_of_work.commits == 0


async def test_a_refused_change_is_neither_saved_nor_committed() -> None:
    tenant = _tenant(status="closed")
    repository = _FakeTenantRepository(tenant)
    unit_of_work = _FakeUnitOfWork()

    with pytest.raises(InvariantViolation):
        await _use_case(repository, unit_of_work).execute(_command(tenant.id))

    assert repository.saved == []
    assert unit_of_work.commits == 0
