"""DA-19: branch names are trimmed, never blank and unique per agency."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest

from lpg.application.common.errors import ConflictError
from lpg.application.tenant.branch import (
    CreateBranchCommand,
    CreateBranchUseCase,
    RenameBranchCommand,
    RenameBranchUseCase,
)
from lpg.domain.common.base import InvariantViolation
from lpg.domain.tenant.branch import Branch

if TYPE_CHECKING:
    from collections.abc import Sequence

_TENANT = uuid.uuid4()


class _Branches:
    def __init__(self, *branches: Branch) -> None:
        self.rows = {b.id: b for b in branches}

    async def get(self, branch_id: uuid.UUID) -> Branch | None:
        return self.rows.get(branch_id)

    async def list_for_tenant(self, tenant_id: uuid.UUID) -> Sequence[Branch]:
        return [b for b in self.rows.values() if b.tenant_id == tenant_id]

    async def add(self, branch: Branch) -> None:
        self.rows[branch.id] = branch

    async def save(self, branch: Branch) -> None:
        self.rows[branch.id] = branch


class _Uow:
    async def commit(self) -> None:
        return None


def _branch(name: str, *, active: bool = True) -> Branch:
    return Branch(uuid.uuid4(), _TENANT, name, is_active=active)


async def test_the_name_is_trimmed() -> None:
    repo = _Branches()
    branch = await CreateBranchUseCase(repo, _Uow()).execute(  # type: ignore[arg-type]
        CreateBranchCommand(tenant_id=_TENANT, name="  Gachibowli  ", region="  ")
    )
    assert branch.name == "Gachibowli"
    assert branch.region is None


async def test_a_blank_name_is_refused() -> None:
    with pytest.raises(InvariantViolation):
        await CreateBranchUseCase(_Branches(), _Uow()).execute(  # type: ignore[arg-type]
            CreateBranchCommand(tenant_id=_TENANT, name="   ")
        )


async def test_a_duplicate_name_is_refused_even_if_inactive_or_differently_cased() -> None:
    repo = _Branches(_branch("Hyderabad Central", active=False))
    with pytest.raises(ConflictError):
        await CreateBranchUseCase(repo, _Uow()).execute(  # type: ignore[arg-type]
            CreateBranchCommand(tenant_id=_TENANT, name=" hyderabad central ")
        )


async def test_another_agency_may_use_the_same_name() -> None:
    other = Branch(uuid.uuid4(), uuid.uuid4(), "Hyderabad Central")
    repo = _Branches(other)
    await CreateBranchUseCase(repo, _Uow()).execute(  # type: ignore[arg-type]
        CreateBranchCommand(tenant_id=_TENANT, name="Hyderabad Central")
    )


async def test_renaming_onto_another_branchs_name_is_refused_but_keeping_it_is_fine() -> None:
    a, b = _branch("North"), _branch("South")
    repo = _Branches(a, b)
    use_case = RenameBranchUseCase(repo, _Uow())  # type: ignore[arg-type]
    with pytest.raises(ConflictError):
        await use_case.execute(RenameBranchCommand(branch_id=b.id, new_name="NORTH"))
    await use_case.execute(RenameBranchCommand(branch_id=a.id, new_name="north"))
    assert a.name == "north"
