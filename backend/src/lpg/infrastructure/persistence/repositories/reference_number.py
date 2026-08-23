from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy.dialects.postgresql import insert as pg_insert

from lpg.infrastructure.persistence.models.platform import ReferenceNumberSequenceModel

if TYPE_CHECKING:
    import uuid

    from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork


class SqlAlchemyReferenceNumberSequence:
    """Generic tenant-scoped reference-number generator, shared by every
    module (`entity_type` distinguishes them) backed by
    `platform.reference_number_sequence`.

    Generalizes `SqlAlchemyConsumerNumberSequence`
    (`repositories/customer.py`) — same `INSERT ... ON CONFLICT ... DO
    UPDATE ... RETURNING` upsert, which Postgres serializes via its own
    row-level lock on the `(tenant_id, entity_type)` row, so concurrent
    callers for the same module never collide without any app-level
    locking — just keyed on the composite `(tenant_id, entity_type)` PK
    instead of `tenant_id` alone, and formatting is configurable per
    instance rather than a hardcoded class-level prefix/pad width.

    Advisory only, same as the consumer-number precedent: uniqueness of the
    *formatted* number is enforced by the caller (a `get_by_*_number`
    collision check), not by this sequence — a peeked-but-unused number is
    simply never reissued, no different from a gap in any database
    sequence.
    """

    def __init__(
        self,
        unit_of_work: SqlAlchemyUnitOfWork,
        tenant_id: uuid.UUID,
        *,
        entity_type: str,
        prefix: str,
        pad_width: int = 6,
        include_year: bool = False,
    ) -> None:
        self._uow = unit_of_work
        self._tenant_id = tenant_id
        self._entity_type = entity_type
        self._prefix = prefix
        self._pad_width = pad_width
        self._include_year = include_year

    async def next(self) -> str:
        stmt = (
            pg_insert(ReferenceNumberSequenceModel)
            .values(tenant_id=self._tenant_id, entity_type=self._entity_type, next_value=2)
            .on_conflict_do_update(
                index_elements=[
                    ReferenceNumberSequenceModel.tenant_id,
                    ReferenceNumberSequenceModel.entity_type,
                ],
                set_={
                    "next_value": ReferenceNumberSequenceModel.next_value + 1,
                },
            )
            .returning(ReferenceNumberSequenceModel.next_value)
        )
        result = await self._uow.session.execute(stmt)
        # The row now holds the *next* value after this one — this call's
        # own number is one less than what was just written.
        new_next_value = result.scalar_one()
        this_value = new_next_value - 1

        digits = f"{this_value:0{self._pad_width}d}"
        if self._include_year:
            year = datetime.now(UTC).year
            return f"{self._prefix}-{year}-{digits}"
        return f"{self._prefix}{digits}"
