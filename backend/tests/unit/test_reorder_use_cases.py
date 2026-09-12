"""Unit tests for the reorder-policy use cases (AI Operational
Intelligence, Horizon 1 Stage 4). Fake repository, no DB.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from lpg.application.inventory.ports import ReorderPolicy, ReorderSignal

if TYPE_CHECKING:
    from collections.abc import Sequence

    from lpg.domain.common.base import DomainEvent
from lpg.application.inventory.reorder import (
    ListReorderPoliciesQuery,
    ListReorderPoliciesUseCase,
    ListReorderSignalsQuery,
    ListReorderSignalsUseCase,
    SetReorderPolicyCommand,
    SetReorderPolicyUseCase,
)


class _FakeUnitOfWork:
    def __init__(self) -> None:
        self.commits = 0

    async def __aenter__(self) -> _FakeUnitOfWork:
        return self

    async def __aexit__(self, *_: object) -> None:
        pass

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        pass

    def collect_events(self) -> Sequence[DomainEvent]:
        return []


class _FakeReorderPolicyRepository:
    def __init__(self) -> None:
        self.upserted: list[dict[str, object]] = []
        self._policies: list[ReorderPolicy] = []
        self._signals: list[ReorderSignal] = []
        self.notified_ids: list[uuid.UUID] = []

    def next_id(self) -> uuid.UUID:
        return uuid.uuid4()

    async def upsert(
        self,
        *,
        tenant_id: uuid.UUID,
        inventory_location_id: uuid.UUID,
        cylinder_type_id: uuid.UUID,
        reorder_point: int,
        safety_stock: int,
        updated_by: uuid.UUID | None,
    ) -> ReorderPolicy:
        self.upserted.append(
            {
                "tenant_id": tenant_id,
                "inventory_location_id": inventory_location_id,
                "cylinder_type_id": cylinder_type_id,
                "reorder_point": reorder_point,
                "safety_stock": safety_stock,
            }
        )
        return ReorderPolicy(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            inventory_location_id=inventory_location_id,
            location_ref_id=uuid.uuid4(),
            cylinder_type_id=cylinder_type_id,
            reorder_point=reorder_point,
            safety_stock=safety_stock,
            last_reorder_notified_at=None,
            updated_by=updated_by,
            updated_at=datetime.now(UTC),
        )

    async def list_for_tenant(self, tenant_id: uuid.UUID) -> list[ReorderPolicy]:
        return [p for p in self._policies if p.tenant_id == tenant_id]

    async def list_breached_for_tenant(
        self,
        tenant_id: uuid.UUID,  # noqa: ARG002 - Protocol keyword-only param
    ) -> list[ReorderSignal]:
        return list(self._signals)

    async def mark_reorder_notified(self, policy_id: uuid.UUID) -> None:
        self.notified_ids.append(policy_id)


@pytest.mark.asyncio
async def test_set_reorder_policy_upserts_and_commits() -> None:
    repo = _FakeReorderPolicyRepository()
    uow = _FakeUnitOfWork()
    tenant_id = uuid.uuid4()
    location_id = uuid.uuid4()
    cylinder_type_id = uuid.uuid4()

    policy = await SetReorderPolicyUseCase(repo, uow).execute(
        SetReorderPolicyCommand(
            tenant_id=tenant_id,
            inventory_location_id=location_id,
            cylinder_type_id=cylinder_type_id,
            reorder_point=20,
            safety_stock=5,
            updated_by=uuid.uuid4(),
        )
    )

    assert policy.reorder_point == 20
    assert policy.safety_stock == 5
    assert len(repo.upserted) == 1
    assert uow.commits == 1


@pytest.mark.asyncio
async def test_list_reorder_policies_scopes_to_tenant() -> None:
    repo = _FakeReorderPolicyRepository()
    tenant_id = uuid.uuid4()
    mine = ReorderPolicy(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        inventory_location_id=uuid.uuid4(),
        location_ref_id=uuid.uuid4(),
        cylinder_type_id=uuid.uuid4(),
        reorder_point=10,
        safety_stock=0,
        last_reorder_notified_at=None,
        updated_by=None,
        updated_at=datetime.now(UTC),
    )
    someone_elses = ReorderPolicy(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        inventory_location_id=uuid.uuid4(),
        location_ref_id=uuid.uuid4(),
        cylinder_type_id=uuid.uuid4(),
        reorder_point=10,
        safety_stock=0,
        last_reorder_notified_at=None,
        updated_by=None,
        updated_at=datetime.now(UTC),
    )
    repo._policies = [mine, someone_elses]

    results = await ListReorderPoliciesUseCase(repo).execute(
        ListReorderPoliciesQuery(tenant_id=tenant_id)
    )
    assert [p.id for p in results] == [mine.id]


@pytest.mark.asyncio
async def test_list_reorder_signals_is_a_pure_read() -> None:
    repo = _FakeReorderPolicyRepository()
    signal = ReorderSignal(
        policy_id=uuid.uuid4(),
        inventory_location_id=uuid.uuid4(),
        location_ref_id=uuid.uuid4(),
        cylinder_type_id=uuid.uuid4(),
        on_hand=2,
        reorder_point=10,
        safety_stock=0,
        last_reorder_notified_at=None,
    )
    repo._signals = [signal]

    results = await ListReorderSignalsUseCase(repo).execute(
        ListReorderSignalsQuery(tenant_id=uuid.uuid4())
    )
    assert list(results) == [signal]
    assert repo.notified_ids == []
