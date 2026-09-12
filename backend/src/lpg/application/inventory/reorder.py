"""Inventory reorder-point alerts — AI Operational Intelligence, Horizon 1
Stage 4.

**v1 scope is warehouses only.** A vehicle's load is transient — refilled
from a warehouse before each route, not something an agency reorders from
its OMC — so only `inventory_location_id`s of `location_type="warehouse"`
are meant to carry a `ReorderPolicy`; nothing in this table enforces that
(same "accepted risk, mitigated at the application layer" note
`4f8b2d6a9c1e`'s own docstring already makes for `location_ref_id`'s lack
of a physical FK), but `SetReorderPolicyUseCase`'s caller
(`api/v1/routers/inventory.py`) only ever resolves a warehouse.

Threshold values are admin-set for v1 — `safety_stock` is carried through
to the read model but not yet used to compute anything (a Horizon-2
`avg_daily_demand x lead_time_days x z` calculation is the documented
follow-up, once the `branch_cylinder_demand` feature family exists).

`ListReorderSignalsUseCase` here is a pure read (no side effects, safe for
a GET endpoint to call on every request). Recording a breach to
`ai.prediction` and deciding whether to notify are the daily cron's own
job (`infrastructure/jobs/inventory_jobs.py`) — mutating on every GET
would violate the read endpoint's own safety, and the cron already needs
its own per-tenant-transaction shape that a shared "check + write" use
case would just get in the way of.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from lpg.application.common.cqrs import Command

if TYPE_CHECKING:
    import uuid
    from collections.abc import Sequence

    from lpg.application.common.ports import UnitOfWork
    from lpg.application.inventory.ports import (
        ReorderPolicy,
        ReorderPolicyRepository,
        ReorderSignal,
    )

#: `ai.prediction.model_version` every reorder-signal row is stamped with
#: (`infrastructure/jobs/inventory_jobs.py`) — a plain threshold
#: comparison, not a trained model, and honestly labelled that way.
MODEL_VERSION = "reorder_threshold_v1"
PREDICTION_TYPE = "reorder_signal"


@dataclass(frozen=True, slots=True)
class SetReorderPolicyCommand(Command):
    tenant_id: uuid.UUID
    inventory_location_id: uuid.UUID
    cylinder_type_id: uuid.UUID
    reorder_point: int
    safety_stock: int
    updated_by: uuid.UUID | None = None


class SetReorderPolicyUseCase:
    def __init__(self, repository: ReorderPolicyRepository, unit_of_work: UnitOfWork) -> None:
        self._repository = repository
        self._unit_of_work = unit_of_work

    async def execute(self, command: SetReorderPolicyCommand) -> ReorderPolicy:
        policy = await self._repository.upsert(
            tenant_id=command.tenant_id,
            inventory_location_id=command.inventory_location_id,
            cylinder_type_id=command.cylinder_type_id,
            reorder_point=command.reorder_point,
            safety_stock=command.safety_stock,
            updated_by=command.updated_by,
        )
        await self._unit_of_work.commit()
        return policy


@dataclass(frozen=True, slots=True)
class ListReorderPoliciesQuery:
    tenant_id: uuid.UUID


class ListReorderPoliciesUseCase:
    def __init__(self, repository: ReorderPolicyRepository) -> None:
        self._repository = repository

    async def execute(self, query: ListReorderPoliciesQuery) -> list[ReorderPolicy]:
        return list(await self._repository.list_for_tenant(query.tenant_id))


@dataclass(frozen=True, slots=True)
class ListReorderSignalsQuery:
    tenant_id: uuid.UUID


class ListReorderSignalsUseCase:
    """Pure read — every currently-breached `(location, cylinder_type)`.
    No `ai.prediction` write, no notification: used by both the read
    endpoint and the daily cron (which adds those two side effects itself
    on top of the same list)."""

    def __init__(self, repository: ReorderPolicyRepository) -> None:
        self._repository = repository

    async def execute(self, query: ListReorderSignalsQuery) -> Sequence[ReorderSignal]:
        return await self._repository.list_breached_for_tenant(query.tenant_id)
