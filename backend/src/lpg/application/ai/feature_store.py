"""`ai.feature_snapshot` — the point-in-time feature store.

One row per `(entity_type, entity_id)` per `as_of_date`, written nightly by
`infrastructure/jobs/feature_store_jobs.py`. A day's snapshot is history —
never rewritten — so a model trained tomorrow sees exactly the features
that existed on the prediction date, not today's current state. That
training-serving parity is the whole reason this table is not a
materialized view.

`features` is an opaque dict the writing job and the reading heuristic
agree on. Horizon 1 writes one family, `customer_refill`; the shapes for
`branch_cylinder_demand` and `route_stop_duration` land in follow-up
commits of this same stage.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    import uuid
    from datetime import date

#: `customer_refill` feature keys — the contract between
#: `build_feature_snapshots` and `PredictRefillDueUseCase` (Stage 2).
ENTITY_CUSTOMER_REFILL = "customer_refill"


@dataclass(frozen=True, slots=True)
class FeatureSnapshot:
    id: uuid.UUID
    tenant_id: uuid.UUID
    entity_type: str
    entity_id: uuid.UUID
    as_of_date: date
    features: dict[str, Any]


@runtime_checkable
class FeatureSnapshotRepository(Protocol):
    def next_id(self) -> uuid.UUID: ...

    async def add_ignoring_conflicts(self, snapshots: list[FeatureSnapshot]) -> int:
        """Bulk-insert; rows whose `(tenant_id, entity_type, entity_id,
        as_of_date)` already exist are silently skipped (`ON CONFLICT DO
        NOTHING`), so re-running the nightly job for the same day is a
        no-op. Returns the number actually inserted."""
        ...

    async def get(
        self, *, entity_type: str, entity_id: uuid.UUID, as_of_date: date
    ) -> FeatureSnapshot | None:
        """The snapshot for one entity on one date (RLS-scoped to the
        current tenant), or `None`. Used by the reading heuristics."""
        ...

    async def latest(
        self, *, entity_type: str, entity_id: uuid.UUID
    ) -> FeatureSnapshot | None:
        """The most recent snapshot for one entity, whatever date — what a
        heuristic run 'today' actually wants when today's job may not have
        run yet."""
        ...

    async def list_latest_by_entity_type(self, *, entity_type: str) -> list[FeatureSnapshot]:
        """Every entity's most recent snapshot for `entity_type`, one row
        per `entity_id` (RLS-scoped to the current tenant) — what a daily
        heuristic cron (Stage 2's `predict_refill_due`) iterates instead of
        re-listing every customer itself."""
        ...
