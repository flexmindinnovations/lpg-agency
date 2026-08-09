"""SQLAlchemy ORM model for `tenant.tenant`.

Deliberately distinct from the `Tenant` domain aggregate
(`lpg.domain.tenant.tenant`) — this is the persistence shape, mapped
one-to-one to the migrated table (`0242df1a3871`); the repository is what
translates between the two (`03-backend-architecture.md` §4).
"""

from __future__ import annotations

# Real imports, not TYPE_CHECKING-guarded: SQLAlchemy's declarative mapper
# resolves `Mapped[...]` annotations via `typing.get_type_hints()` at
# mapper-configuration time, which needs `uuid`/`datetime` present in this
# module's runtime namespace — unlike a plain dataclass, hiding them behind
# `if TYPE_CHECKING:` breaks the mapping.
import uuid  # noqa: TC003
from datetime import datetime  # noqa: TC003

from sqlalchemy import Boolean, DateTime, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from lpg.infrastructure.persistence.database import Base


class TenantModel(Base):
    """Maps every column the migration created, not only the ones this
    phase's repository happens to touch — an ORM model with gaps against its
    own table is exactly what makes a later `alembic revision --autogenerate`
    propose dropping columns nobody meant to remove."""

    __tablename__ = "tenant"
    # SQLAlchemy's own declarative base already types __table_args__ as an
    # instance attribute; annotating it ClassVar here to satisfy ruff's
    # RUF012 (mutable class default) conflicts with that under
    # mypy --strict. SQLAlchemy only ever reads this once, at
    # mapper-configuration time — it is not a mutable-default footgun in
    # practice, so the rule is suppressed rather than fought.
    __table_args__ = {"schema": "tenant"}  # noqa: RUF012

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_by: Mapped[uuid.UUID | None] = mapped_column(Uuid())
    is_deleted: Mapped[bool] = mapped_column(Boolean())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_by: Mapped[uuid.UUID | None] = mapped_column(Uuid())
    version: Mapped[int] = mapped_column(Integer())
