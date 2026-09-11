"""`ai.prediction` — the traceability spine for AI Operational Intelligence.

Every number a heuristic (Horizon 1) or a trained model (Horizon 2) puts
in front of a user is recorded here first, tagged with the `model_version`
that produced it and a hash of its inputs. Nothing about the prediction is
editable after the fact — a corrected prediction is a new row. This is
what makes a displayed forecast attributable, and a heuristic → model swap
observable.

Same "plain record, not an `AggregateRoot`" shape as `AssistantRun` /
`WeighmentRecord`: written via `add()` inside the caller's own `UnitOfWork`,
riding `AuditRecorder`'s generic `before_flush` hook for a free audit
trail — no bespoke audit-write path.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from lpg.application.common.cqrs import Command

if TYPE_CHECKING:
    import uuid
    from datetime import datetime
    from decimal import Decimal


@dataclass(frozen=True, slots=True)
class Prediction:
    """One recorded prediction. `value` is any JSON-safe dict — the shape is
    the caller's business (`{"refill_due_date": "..."}`,
    `{"shortfall": 12}`, `{"ordered_stop_ids": [...], "km_saved": 4.2}`)."""

    id: uuid.UUID
    tenant_id: uuid.UUID
    prediction_type: str
    subject_type: str
    subject_id: uuid.UUID
    model_version: str
    value: dict[str, Any]
    input_hash: str | None = None
    confidence: Decimal | None = None
    created_at: datetime | None = None


@runtime_checkable
class PredictionRepository(Protocol):
    def next_id(self) -> uuid.UUID: ...

    async def add(self, prediction: Prediction) -> None: ...

    async def latest_for_subject(
        self, *, prediction_type: str, subject_id: uuid.UUID
    ) -> Prediction | None:
        """The most recent prediction of this type about this subject
        (RLS-scoped to the current tenant, same convention as
        `AssistantRunRepository.get_todays_token_usage`). Used by the
        read-side endpoints that surface predictions in the UI."""
        ...

    async def list_latest_by_type(self, *, prediction_type: str) -> list[Prediction]:
        """Every subject's most recent prediction of this type, one row per
        `subject_id` (RLS-scoped to the current tenant) — what a dashboard
        read endpoint (`GET /customers/refill-due`, Stage 2) lists instead
        of querying per-subject one at a time."""
        ...


def hash_inputs(inputs: dict[str, Any]) -> str:
    """A stable SHA-256 over the feature inputs, so an identical
    re-computation is recognisable and a changed input is visible in the
    prediction history. Keys are sorted; values must be JSON-serialisable."""
    canonical = json.dumps(inputs, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class RecordPredictionCommand(Command):
    tenant_id: uuid.UUID
    prediction_type: str
    subject_type: str
    subject_id: uuid.UUID
    model_version: str
    value: dict[str, Any]
    inputs: dict[str, Any] | None = None
    confidence: Decimal | None = None


class RecordPredictionUseCase:
    """Persists one prediction. Deliberately tiny — it exists so every
    heuristic job goes through one named, testable seam rather than each
    hand-rolling a repository `add()`. `tenant_id` is supplied explicitly
    (the job already holds it from its `RequestTenantContext`), matching
    `AskAiAssistantUseCase`'s own `AssistantRun(tenant_id=principal.tenant_id)`
    shape — the RLS `WITH CHECK` on `ai.prediction` rejects a mismatched id."""

    def __init__(self, prediction_repository: PredictionRepository) -> None:
        self._repository = prediction_repository

    async def execute(self, command: RecordPredictionCommand) -> uuid.UUID:
        prediction_id = self._repository.next_id()
        await self._repository.add(
            Prediction(
                id=prediction_id,
                tenant_id=command.tenant_id,
                prediction_type=command.prediction_type,
                subject_type=command.subject_type,
                subject_id=command.subject_id,
                model_version=command.model_version,
                value=command.value,
                input_hash=hash_inputs(command.inputs) if command.inputs is not None else None,
                confidence=command.confidence,
            )
        )
        return prediction_id
