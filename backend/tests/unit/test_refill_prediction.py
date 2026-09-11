"""Unit tests for the refill-due heuristic (AI Operational Intelligence,
Horizon 1 Stage 2). Fake repositories, no DB.
"""

from __future__ import annotations

import uuid
from datetime import date

import pytest

from lpg.application.ai.feature_store import ENTITY_CUSTOMER_REFILL, FeatureSnapshot
from lpg.application.ai.prediction import Prediction
from lpg.application.customer.refill_prediction import (
    MIN_DELIVERIES_FOR_OWN_INTERVAL,
    MODEL_VERSION,
    ListRefillDueCustomersQuery,
    ListRefillDueCustomersUseCase,
    PredictRefillDueForCustomerCommand,
    PredictRefillDueUseCase,
    compute_shrunk_interval,
)
from lpg.domain.customer.customer import Customer


class _FakeFeatureSnapshotRepository:
    def __init__(self, snapshots: dict[uuid.UUID, FeatureSnapshot]) -> None:
        self._snapshots = snapshots

    def next_id(self) -> uuid.UUID:
        return uuid.uuid4()

    async def add_ignoring_conflicts(self, snapshots: list[FeatureSnapshot]) -> int:
        raise NotImplementedError

    async def get(
        self, *, entity_type: str, entity_id: uuid.UUID, as_of_date: date
    ) -> FeatureSnapshot | None:
        raise NotImplementedError

    async def latest(
        self,
        *,
        entity_type: str,  # noqa: ARG002 - Protocol keyword-only param
        entity_id: uuid.UUID,
    ) -> FeatureSnapshot | None:
        return self._snapshots.get(entity_id)

    async def list_latest_by_entity_type(
        self,
        *,
        entity_type: str,  # noqa: ARG002 - Protocol keyword-only param
    ) -> list[FeatureSnapshot]:
        return list(self._snapshots.values())


class _FakePredictionRepository:
    def __init__(self) -> None:
        self.added: list[Prediction] = []

    def next_id(self) -> uuid.UUID:
        return uuid.uuid4()

    async def add(self, prediction: Prediction) -> None:
        self.added.append(prediction)

    async def latest_for_subject(
        self,
        *,
        prediction_type: str,  # noqa: ARG002 - Protocol keyword-only param
        subject_id: uuid.UUID,
    ) -> Prediction | None:
        matches = [p for p in self.added if p.subject_id == subject_id]
        return matches[-1] if matches else None

    async def list_latest_by_type(self, *, prediction_type: str) -> list[Prediction]:
        return [p for p in self.added if p.prediction_type == prediction_type]


class _FakeCustomerRepository:
    def __init__(self, customers: dict[uuid.UUID, Customer]) -> None:
        self._customers = customers

    def next_id(self) -> uuid.UUID:
        return uuid.uuid4()

    async def save(self, customer: Customer) -> None:
        raise NotImplementedError

    async def get_by_id(self, customer_id: uuid.UUID) -> Customer | None:
        return self._customers.get(customer_id)

    async def get_by_phone(self, phone_number: str) -> Customer | None:
        raise NotImplementedError

    async def get_by_consumer_number(self, consumer_number: str) -> Customer | None:
        raise NotImplementedError

    async def get_by_lpg_subsidy_id(self, lpg_subsidy_id: str) -> Customer | None:
        raise NotImplementedError

    async def get_by_identity_user_id(self, identity_user_id: uuid.UUID) -> Customer | None:
        raise NotImplementedError

    async def list_customers(
        self, skip: int = 0, limit: int = 100, search: str | None = None
    ) -> list[Customer]:
        raise NotImplementedError

    async def count_customers(self, search: str | None = None) -> int:
        raise NotImplementedError

    async def get_last_refill_nudge_sent_at(self, customer_id: uuid.UUID) -> None:
        raise NotImplementedError

    async def mark_refill_nudge_sent(self, customer_id: uuid.UUID) -> None:
        raise NotImplementedError


def _snapshot(
    customer_id: uuid.UUID,
    *,
    last_delivered_at: str | None,
    delivery_count: int,
    avg_refill_interval_days: float | None,
    branch_id: uuid.UUID | None = None,
) -> FeatureSnapshot:
    return FeatureSnapshot(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        entity_type=ENTITY_CUSTOMER_REFILL,
        entity_id=customer_id,
        as_of_date=date(2026, 9, 11),
        features={
            "last_delivered_at": last_delivered_at,
            "delivery_count": delivery_count,
            "avg_refill_interval_days": avg_refill_interval_days,
            "branch_id": str(branch_id) if branch_id else None,
            "primary_cylinder_type_id": None,
        },
    )


# --- compute_shrunk_interval -------------------------------------------


def test_full_trust_in_own_interval_once_enough_deliveries() -> None:
    interval = compute_shrunk_interval(
        own_avg_interval_days=20.0,
        own_delivery_count=MIN_DELIVERIES_FOR_OWN_INTERVAL,
        population_mean_interval_days=30.0,
    )
    assert interval == 20.0


def test_blends_toward_population_mean_for_a_sparse_customer() -> None:
    # 1 of 4 deliveries worth of trust -> 25% own, 75% population.
    interval = compute_shrunk_interval(
        own_avg_interval_days=20.0,
        own_delivery_count=1,
        population_mean_interval_days=30.0,
    )
    assert interval == pytest.approx(0.25 * 20.0 + 0.75 * 30.0)


def test_falls_back_to_population_mean_with_no_own_interval() -> None:
    interval = compute_shrunk_interval(
        own_avg_interval_days=None, own_delivery_count=0, population_mean_interval_days=30.0
    )
    assert interval == 30.0


def test_falls_back_to_own_interval_with_no_population_mean() -> None:
    interval = compute_shrunk_interval(
        own_avg_interval_days=20.0, own_delivery_count=1, population_mean_interval_days=None
    )
    assert interval == 20.0


def test_none_when_neither_interval_is_known() -> None:
    interval = compute_shrunk_interval(
        own_avg_interval_days=None, own_delivery_count=0, population_mean_interval_days=None
    )
    assert interval is None


# --- PredictRefillDueUseCase ---------------------------------------------


@pytest.mark.asyncio
async def test_predicts_and_records_refill_due_date() -> None:
    tenant_id = uuid.uuid4()
    customer_id = uuid.uuid4()
    branch_id = uuid.uuid4()
    snapshot_repo = _FakeFeatureSnapshotRepository(
        {
            customer_id: _snapshot(
                customer_id,
                last_delivered_at="2026-09-01T00:00:00+00:00",
                delivery_count=MIN_DELIVERIES_FOR_OWN_INTERVAL,
                avg_refill_interval_days=20.0,
                branch_id=branch_id,
            )
        }
    )
    prediction_repo = _FakePredictionRepository()

    result = await PredictRefillDueUseCase(snapshot_repo, prediction_repo).execute(
        PredictRefillDueForCustomerCommand(
            tenant_id=tenant_id,
            customer_id=customer_id,
            as_of=date(2026, 9, 11),
            population_mean_interval_days=30.0,
        )
    )

    assert result is not None
    assert result.last_delivered_at == date(2026, 9, 1)
    assert result.interval_days == 20.0
    assert result.refill_due_date == date(2026, 9, 21)
    assert result.branch_id == branch_id

    assert len(prediction_repo.added) == 1
    recorded = prediction_repo.added[0]
    assert recorded.tenant_id == tenant_id
    assert recorded.subject_id == customer_id
    assert recorded.subject_type == "customer"
    assert recorded.prediction_type == "refill_due"
    assert recorded.model_version == MODEL_VERSION
    assert recorded.value["refill_due_date"] == "2026-09-21"


@pytest.mark.asyncio
async def test_returns_none_without_a_snapshot() -> None:
    snapshot_repo = _FakeFeatureSnapshotRepository({})
    prediction_repo = _FakePredictionRepository()

    result = await PredictRefillDueUseCase(snapshot_repo, prediction_repo).execute(
        PredictRefillDueForCustomerCommand(
            tenant_id=uuid.uuid4(),
            customer_id=uuid.uuid4(),
            as_of=date(2026, 9, 11),
            population_mean_interval_days=30.0,
        )
    )
    assert result is None
    assert prediction_repo.added == []


@pytest.mark.asyncio
async def test_returns_none_without_any_delivery_on_record() -> None:
    customer_id = uuid.uuid4()
    snapshot_repo = _FakeFeatureSnapshotRepository(
        {
            customer_id: _snapshot(
                customer_id,
                last_delivered_at=None,
                delivery_count=0,
                avg_refill_interval_days=None,
            )
        }
    )
    prediction_repo = _FakePredictionRepository()

    result = await PredictRefillDueUseCase(snapshot_repo, prediction_repo).execute(
        PredictRefillDueForCustomerCommand(
            tenant_id=uuid.uuid4(),
            customer_id=customer_id,
            as_of=date(2026, 9, 11),
            population_mean_interval_days=30.0,
        )
    )
    assert result is None


# --- ListRefillDueCustomersUseCase ----------------------------------------


@pytest.mark.asyncio
async def test_lists_only_customers_due_within_the_window_earliest_first() -> None:
    tenant_id = uuid.uuid4()
    branch_id = uuid.uuid4()
    due_soon_id = uuid.uuid4()
    overdue_id = uuid.uuid4()
    far_out_id = uuid.uuid4()

    customers = {
        due_soon_id: Customer(due_soon_id, tenant_id, branch_id, "Due Soon", "+919876500001"),
        overdue_id: Customer(overdue_id, tenant_id, branch_id, "Overdue", "+919876500002"),
        far_out_id: Customer(far_out_id, tenant_id, branch_id, "Far Out", "+919876500003"),
    }
    customer_repo = _FakeCustomerRepository(customers)

    prediction_repo = _FakePredictionRepository()
    prediction_repo.added = [
        Prediction(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            prediction_type="refill_due",
            subject_type="customer",
            subject_id=due_soon_id,
            model_version=MODEL_VERSION,
            value={
                "refill_due_date": "2026-09-15",
                "interval_days": 20.0,
                "last_delivered_at": "2026-08-26",
            },
        ),
        Prediction(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            prediction_type="refill_due",
            subject_type="customer",
            subject_id=overdue_id,
            model_version=MODEL_VERSION,
            value={
                "refill_due_date": "2026-09-05",
                "interval_days": 18.0,
                "last_delivered_at": "2026-08-18",
            },
        ),
        Prediction(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            prediction_type="refill_due",
            subject_type="customer",
            subject_id=far_out_id,
            model_version=MODEL_VERSION,
            value={
                "refill_due_date": "2026-10-10",
                "interval_days": 40.0,
                "last_delivered_at": "2026-08-30",
            },
        ),
    ]

    results = await ListRefillDueCustomersUseCase(prediction_repo, customer_repo).execute(
        ListRefillDueCustomersQuery(as_of=date(2026, 9, 11), within_days=7)
    )

    assert [r.customer_id for r in results] == [overdue_id, due_soon_id]
