"""Refill-due prediction — AI Operational Intelligence, Horizon 1 Stage 2.

The first user-visible heuristic: `refill_due_date = last_delivered_at +
interval`, where `interval` is the customer's own rolling average refill
gap (`ai.feature_snapshot`'s `customer_refill` family, itself sourced from
`rpt.mv_customer_consumption`), shrunk toward the tenant-wide average when
the customer doesn't have enough delivery history of their own to trust in
isolation.

**Deviation from the original plan, made honestly:** the plan called for
shrinking toward the `branch x cylinder_type` mean interval. That feature
family (`branch_cylinder_demand`) doesn't exist yet — it's a Stage 4
follow-up (inventory reorder-point alerts need it too, and building it
just for this would be guessing at a shape before there's a second real
consumer). Shrinking toward the simpler tenant-wide mean interval instead
is a smaller, honestly-labelled v1: still a real guardrail against a
brand-new customer's estimate coming from a single noisy gap, and it's the
same "call `compute_shrunk_interval` again with a better population mean"
seam a `branch_cylinder_demand`-based version would slot into later — no
call site elsewhere in this module needs to change when that happens.

Written to `ai.prediction` (`prediction_type="refill_due"`,
`model_version=MODEL_VERSION`) so every displayed due-date is traceable,
per `application/ai/prediction.py`'s own contract.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from lpg.application.ai.feature_store import ENTITY_CUSTOMER_REFILL
from lpg.application.ai.prediction import RecordPredictionCommand, RecordPredictionUseCase

if TYPE_CHECKING:
    from datetime import date

    from lpg.application.ai.feature_store import FeatureSnapshotRepository
    from lpg.application.ai.prediction import PredictionRepository
    from lpg.application.customer.ports import CustomerRepository

#: A customer's own average interval is trusted alone once they have this
#: many delivered orders behind it (`ai.feature_snapshot.features.
#: delivery_count`); below that it's blended with the tenant-wide mean,
#: linearly by how much of their own history backs the estimate (Phase 22
#: Slice A's guardrail against nudging sparse customers off a fluke gap).
MIN_DELIVERIES_FOR_OWN_INTERVAL = 4

#: `ai.prediction.model_version` for every row this module writes. Bump
#: this (not the class name) when the heuristic's formula changes, so old
#: predictions stay attributable to the formula that actually produced
#: them.
MODEL_VERSION = "refill_heuristic_v1"

PREDICTION_TYPE = "refill_due"


def compute_shrunk_interval(
    *,
    own_avg_interval_days: float | None,
    own_delivery_count: int,
    population_mean_interval_days: float | None,
    min_deliveries: int = MIN_DELIVERIES_FOR_OWN_INTERVAL,
) -> float | None:
    """Blends a customer's own rolling refill interval with the tenant-wide
    mean, weighted by how much of their own history backs the estimate — a
    customer with `min_deliveries` deliveries or more is trusted fully; one
    with none leans entirely on the population mean. Pure function, no I/O,
    so it's independently unit- and backtest-able
    (`tests/evaluation/test_refill_heuristic.py`).

    Returns `None` only when neither number exists — nothing to predict
    from yet (a brand-new tenant with no delivery history anywhere)."""
    if own_avg_interval_days is None:
        return population_mean_interval_days
    if population_mean_interval_days is None:
        return own_avg_interval_days
    weight = min(own_delivery_count / min_deliveries, 1.0) if min_deliveries > 0 else 1.0
    return weight * own_avg_interval_days + (1 - weight) * population_mean_interval_days


@dataclass(frozen=True, slots=True)
class RefillDuePrediction:
    customer_id: uuid.UUID
    branch_id: uuid.UUID | None
    last_delivered_at: date
    interval_days: float
    refill_due_date: date
    delivery_count: int


@dataclass(frozen=True, slots=True)
class PredictRefillDueForCustomerCommand:
    tenant_id: uuid.UUID
    customer_id: uuid.UUID
    as_of: date
    #: Computed once per tenant per cron run by the caller (the mean
    #: `avg_refill_interval_days` across every customer_refill snapshot
    #: that has one) — passed in rather than queried per customer so N
    #: customers cost one population scan, not N.
    population_mean_interval_days: float | None


class PredictRefillDueUseCase:
    """Reads one customer's latest `customer_refill` feature snapshot,
    blends the interval, records the result to `ai.prediction`, and
    returns it so the caller (the daily cron, or a read endpoint computing
    on demand) can act on it. Returns `None` when there isn't enough
    history to predict from (no snapshot yet, or no delivery on record)."""

    def __init__(
        self,
        feature_snapshot_repository: FeatureSnapshotRepository,
        prediction_repository: PredictionRepository,
    ) -> None:
        self._feature_snapshot_repository = feature_snapshot_repository
        self._prediction_repository = prediction_repository

    async def execute(
        self, command: PredictRefillDueForCustomerCommand
    ) -> RefillDuePrediction | None:
        snapshot = await self._feature_snapshot_repository.latest(
            entity_type=ENTITY_CUSTOMER_REFILL, entity_id=command.customer_id
        )
        if snapshot is None:
            return None
        features = snapshot.features
        last_delivered_raw = features.get("last_delivered_at")
        if not last_delivered_raw:
            return None
        last_delivered_at = datetime.fromisoformat(str(last_delivered_raw)).date()
        delivery_count = int(features.get("delivery_count") or 0)
        own_avg_raw = features.get("avg_refill_interval_days")
        own_avg = float(own_avg_raw) if own_avg_raw is not None else None

        interval = compute_shrunk_interval(
            own_avg_interval_days=own_avg,
            own_delivery_count=delivery_count,
            population_mean_interval_days=command.population_mean_interval_days,
        )
        if interval is None or interval <= 0:
            return None

        refill_due_date = last_delivered_at + timedelta(days=round(interval))
        branch_id_raw = features.get("branch_id")

        prediction = RefillDuePrediction(
            customer_id=command.customer_id,
            branch_id=uuid.UUID(str(branch_id_raw)) if branch_id_raw else None,
            last_delivered_at=last_delivered_at,
            interval_days=interval,
            refill_due_date=refill_due_date,
            delivery_count=delivery_count,
        )

        await RecordPredictionUseCase(self._prediction_repository).execute(
            RecordPredictionCommand(
                tenant_id=command.tenant_id,
                prediction_type=PREDICTION_TYPE,
                subject_type="customer",
                subject_id=command.customer_id,
                model_version=MODEL_VERSION,
                value={
                    "refill_due_date": refill_due_date.isoformat(),
                    "interval_days": interval,
                    "last_delivered_at": last_delivered_at.isoformat(),
                },
                inputs={
                    "own_avg_interval_days": own_avg,
                    "delivery_count": delivery_count,
                    "population_mean_interval_days": command.population_mean_interval_days,
                    "as_of": command.as_of.isoformat(),
                },
            )
        )
        return prediction


@dataclass(frozen=True, slots=True)
class RefillDueCustomer:
    """One row of the 'refills due soon' read model — a prediction joined
    back to the customer it's about, for the dashboard tile / list."""

    customer_id: uuid.UUID
    full_name: str
    phone_number: str
    branch_id: uuid.UUID
    refill_due_date: date
    interval_days: float
    last_delivered_at: date


@dataclass(frozen=True, slots=True)
class ListRefillDueCustomersQuery:
    as_of: date
    #: Include a customer whose `refill_due_date` falls within this many
    #: days of `as_of` — negative (already overdue) is included too, since
    #: that's the most urgent case, not an edge case to filter out.
    within_days: int = 7


class ListRefillDueCustomersUseCase:
    """Reads the latest `refill_due` prediction for every customer and
    returns the ones due within the window, earliest first. Read-only —
    does not compute anything new; `predict_refill_due` (the daily cron)
    is what keeps these predictions fresh."""

    def __init__(
        self,
        prediction_repository: PredictionRepository,
        customer_repository: CustomerRepository,
    ) -> None:
        self._prediction_repository = prediction_repository
        self._customer_repository = customer_repository

    async def execute(self, query: ListRefillDueCustomersQuery) -> list[RefillDueCustomer]:
        predictions = await self._prediction_repository.list_latest_by_type(
            prediction_type=PREDICTION_TYPE
        )
        cutoff = query.as_of + timedelta(days=query.within_days)

        results: list[RefillDueCustomer] = []
        for prediction in predictions:
            due_raw = prediction.value.get("refill_due_date")
            if not due_raw:
                continue
            refill_due_date = datetime.fromisoformat(str(due_raw)).date()
            if refill_due_date > cutoff:
                continue
            customer = await self._customer_repository.get_by_id(prediction.subject_id)
            if customer is None:
                continue
            results.append(
                RefillDueCustomer(
                    customer_id=customer.id,
                    full_name=customer.full_name,
                    phone_number=customer.phone_number,
                    branch_id=customer.branch_id,
                    refill_due_date=refill_due_date,
                    interval_days=float(prediction.value.get("interval_days") or 0),
                    last_delivered_at=datetime.fromisoformat(
                        str(prediction.value.get("last_delivered_at"))
                    ).date(),
                )
            )

        results.sort(key=lambda r: r.refill_due_date)
        return results
