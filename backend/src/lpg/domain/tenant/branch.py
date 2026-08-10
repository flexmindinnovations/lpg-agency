"""The `Branch` aggregate — a tenant's physical operating location.

Phase 7 (Administration). Its own aggregate root, not an entity nested
inside `Tenant` — every other "master data" table in this codebase (the
`identity` module's `role`/`permission`, `Tenant` itself) already follows
one-aggregate-per-table, and loading the whole `Tenant` graph to rename one
branch would be impractical. `01-domain-model.md` §4.1 is corrected to match
this (see `planning/features/07-administration-tenant-master-data/PLAN.md`).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from lpg.domain.common.base import AggregateRoot, DomainEvent, InvariantViolation

if TYPE_CHECKING:
    import uuid


@dataclass(frozen=True, slots=True)
class BranchRenamed(DomainEvent):
    branch_id: uuid.UUID | None = None
    new_name: str = ""


class Branch(AggregateRoot):
    __slots__ = ("_name", "_region", "_tenant_id")

    def __init__(
        self,
        branch_id: uuid.UUID,
        tenant_id: uuid.UUID,
        name: str,
        region: str | None = None,
        *,
        version: int = 1,
    ) -> None:
        super().__init__(branch_id, version=version)
        self._tenant_id = tenant_id
        self._name = name
        self._region = region

    @property
    def tenant_id(self) -> uuid.UUID:
        return self._tenant_id

    @property
    def name(self) -> str:
        return self._name

    @property
    def region(self) -> str | None:
        return self._region

    def rename(self, new_name: str) -> None:
        stripped = new_name.strip()
        if not stripped:
            msg = "Branch name cannot be empty."
            raise InvariantViolation(msg, branch_id=str(self.id))

        self._name = stripped
        self.record_event(BranchRenamed(branch_id=self.id, new_name=stripped))

    def set_region(self, region: str | None) -> None:
        self._region = region.strip() if region else None
