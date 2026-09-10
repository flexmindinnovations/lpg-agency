"""SQLAlchemy implementations of the `ai` bounded context's repositories.

All queries are tenant-scoped via Row-Level Security on the `ai.*` tables.
Implements `lpg.application.ai.ports.AssistantRunRepository` and
`lpg.application.ai.prediction.PredictionRepository`.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from lpg.application.ai.feature_store import FeatureSnapshot
from lpg.application.ai.prediction import Prediction
from lpg.infrastructure.persistence.models.ai import (
    AssistantRunModel,
    FeatureSnapshotModel,
    PredictionModel,
)

if TYPE_CHECKING:
    from datetime import date

    from sqlalchemy import CursorResult

    from lpg.application.ai.ports import AssistantRun
    from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork


class SqlAlchemyAssistantRunRepository:
    """Append-only — no `save`/update path, matching
    `SqlAlchemyWeighmentRecordRepository`'s own shape. Not an `AggregateRoot`
    repository: no `register_aggregate`/event-dispatch, just `add`."""

    def __init__(self, unit_of_work: SqlAlchemyUnitOfWork) -> None:
        self._uow = unit_of_work

    def next_id(self) -> uuid.UUID:
        return uuid.uuid4()

    async def add(self, run: AssistantRun) -> None:
        self._uow.session.add(
            AssistantRunModel(
                id=run.id,
                tenant_id=run.tenant_id,
                user_id=run.user_id,
                role=run.role,
                question=run.question,
                tools_used=run.tools_used,
                provider=run.provider,
                model=run.model,
                prompt_tokens=run.prompt_tokens,
                completion_tokens=run.completion_tokens,
                tool_turns=run.tool_turns,
                latency_ms=run.latency_ms,
                status=run.status,
                error_message=run.error_message,
                correlation_id=run.correlation_id,
            )
        )

    async def get_todays_token_usage(self) -> int:
        now = datetime.now(UTC)
        start_of_today = datetime(now.year, now.month, now.day, tzinfo=UTC)
        stmt = select(
            func.coalesce(
                func.sum(AssistantRunModel.prompt_tokens + AssistantRunModel.completion_tokens),
                0,
            )
        ).where(AssistantRunModel.created_at >= start_of_today)
        result = await self._uow.session.execute(stmt)
        return int(result.scalar_one())


class SqlAlchemyPredictionRepository:
    """Append-only — `add` + read, no update path, matching
    `SqlAlchemyAssistantRunRepository`'s shape. Not an `AggregateRoot`
    repository."""

    def __init__(self, unit_of_work: SqlAlchemyUnitOfWork) -> None:
        self._uow = unit_of_work

    def next_id(self) -> uuid.UUID:
        return uuid.uuid4()

    async def add(self, prediction: Prediction) -> None:
        self._uow.session.add(
            PredictionModel(
                id=prediction.id,
                tenant_id=prediction.tenant_id,
                prediction_type=prediction.prediction_type,
                subject_type=prediction.subject_type,
                subject_id=prediction.subject_id,
                model_version=prediction.model_version,
                input_hash=prediction.input_hash,
                value=prediction.value,
                confidence=prediction.confidence,
            )
        )

    async def latest_for_subject(
        self, *, prediction_type: str, subject_id: uuid.UUID
    ) -> Prediction | None:
        stmt = (
            select(PredictionModel)
            .where(
                PredictionModel.prediction_type == prediction_type,
                PredictionModel.subject_id == subject_id,
            )
            .order_by(PredictionModel.created_at.desc())
            .limit(1)
        )
        row = (await self._uow.session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return None
        return Prediction(
            id=row.id,
            tenant_id=row.tenant_id,
            prediction_type=row.prediction_type,
            subject_type=row.subject_type,
            subject_id=row.subject_id,
            model_version=row.model_version,
            value=row.value,
            input_hash=row.input_hash,
            confidence=row.confidence,
            created_at=row.created_at,
        )


class SqlAlchemyFeatureSnapshotRepository:
    """Append-only point-in-time feature store. `add_ignoring_conflicts`
    uses PostgreSQL `ON CONFLICT DO NOTHING` so the nightly job is
    idempotent on re-run."""

    def __init__(self, unit_of_work: SqlAlchemyUnitOfWork) -> None:
        self._uow = unit_of_work

    def next_id(self) -> uuid.UUID:
        return uuid.uuid4()

    async def add_ignoring_conflicts(self, snapshots: list[FeatureSnapshot]) -> int:
        if not snapshots:
            return 0
        stmt = pg_insert(FeatureSnapshotModel).values(
            [
                {
                    "id": s.id,
                    "tenant_id": s.tenant_id,
                    "entity_type": s.entity_type,
                    "entity_id": s.entity_id,
                    "as_of_date": s.as_of_date,
                    "features": s.features,
                }
                for s in snapshots
            ]
        )
        stmt = stmt.on_conflict_do_nothing(constraint="uq_ai_feature_snapshot_dimension")
        result = cast("CursorResult[Any]", await self._uow.session.execute(stmt))
        return result.rowcount or 0

    async def get(
        self, *, entity_type: str, entity_id: uuid.UUID, as_of_date: date
    ) -> FeatureSnapshot | None:
        stmt = select(FeatureSnapshotModel).where(
            FeatureSnapshotModel.entity_type == entity_type,
            FeatureSnapshotModel.entity_id == entity_id,
            FeatureSnapshotModel.as_of_date == as_of_date,
        )
        row = (await self._uow.session.execute(stmt)).scalar_one_or_none()
        return _to_feature_snapshot(row) if row is not None else None

    async def latest(
        self, *, entity_type: str, entity_id: uuid.UUID
    ) -> FeatureSnapshot | None:
        stmt = (
            select(FeatureSnapshotModel)
            .where(
                FeatureSnapshotModel.entity_type == entity_type,
                FeatureSnapshotModel.entity_id == entity_id,
            )
            .order_by(FeatureSnapshotModel.as_of_date.desc())
            .limit(1)
        )
        row = (await self._uow.session.execute(stmt)).scalar_one_or_none()
        return _to_feature_snapshot(row) if row is not None else None


def _to_feature_snapshot(row: FeatureSnapshotModel) -> FeatureSnapshot:
    return FeatureSnapshot(
        id=row.id,
        tenant_id=row.tenant_id,
        entity_type=row.entity_type,
        entity_id=row.entity_id,
        as_of_date=row.as_of_date,
        features=row.features,
    )
