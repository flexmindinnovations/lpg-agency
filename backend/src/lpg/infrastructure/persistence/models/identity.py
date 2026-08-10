"""SQLAlchemy ORM models for the `identity` schema.

Deliberately distinct from the domain aggregates (`lpg.domain.identity.*`) —
these are the persistence shapes, mapped one-to-one to the migrated tables
(`fa52b77ec442`, `10a62de534be`); the repositories translate between the two
(`03-backend-architecture.md` §4), matching `models/tenant.py`'s pattern.

`IdentityUserModel`'s `is_active`/`failed_login_count`/`created_at`/
`updated_at`/`is_deleted`/`version` mirror the migration's `server_default`s
here too — every write against this table before Phase 7 went through a
`SECURITY DEFINER` SQL function (`auth_bootstrap` paths), never a plain
`session.add(...)`, so this gap (same one `models/tenant.py`'s module
docstring documents finding) was latent until `StaffUserRepository.add()`
became the first ORM-level insert against `identity_user`.
"""

from __future__ import annotations

# Real imports, not TYPE_CHECKING-guarded — see the identical note in
# lpg.infrastructure.persistence.models.tenant.
import uuid  # noqa: TC003
from datetime import datetime  # noqa: TC003

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from lpg.infrastructure.persistence.database import Base


class RoleModel(Base):
    __tablename__ = "role"
    __table_args__ = {"schema": "identity"}  # noqa: RUF012 - see tenant.py's identical note

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True)
    code: Mapped[str] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_by: Mapped[uuid.UUID | None] = mapped_column(Uuid())
    is_deleted: Mapped[bool] = mapped_column(Boolean())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_by: Mapped[uuid.UUID | None] = mapped_column(Uuid())
    version: Mapped[int] = mapped_column(Integer())


class PermissionModel(Base):
    __tablename__ = "permission"
    __table_args__ = {"schema": "identity"}  # noqa: RUF012

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True)
    code: Mapped[str] = mapped_column(String(100))
    resource: Mapped[str] = mapped_column(String(50))
    action: Mapped[str] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_by: Mapped[uuid.UUID | None] = mapped_column(Uuid())
    is_deleted: Mapped[bool] = mapped_column(Boolean())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_by: Mapped[uuid.UUID | None] = mapped_column(Uuid())
    version: Mapped[int] = mapped_column(Integer())


class RolePermissionModel(Base):
    __tablename__ = "role_permission"
    __table_args__ = {"schema": "identity"}  # noqa: RUF012

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True)
    role_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("identity.role.id"))
    permission_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("identity.permission.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class IdentityUserModel(Base):
    __tablename__ = "identity_user"
    __table_args__ = {"schema": "identity"}  # noqa: RUF012

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True)
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(Uuid())
    branch_id: Mapped[uuid.UUID | None] = mapped_column(Uuid())
    email: Mapped[str | None] = mapped_column(String(320))
    phone_number: Mapped[str | None] = mapped_column(String(20))
    password_hash: Mapped[str | None] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(50))
    is_active: Mapped[bool] = mapped_column(Boolean(), server_default=text("true"))
    failed_login_count: Mapped[int] = mapped_column(Integer(), server_default=text("0"))
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sso_subject: Mapped[str | None] = mapped_column(String(200))
    sso_provider: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(Uuid())
    is_deleted: Mapped[bool] = mapped_column(Boolean(), server_default=text("false"))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_by: Mapped[uuid.UUID | None] = mapped_column(Uuid())
    version: Mapped[int] = mapped_column(Integer(), server_default=text("1"))


class UserRoleModel(Base):
    __tablename__ = "user_role"
    __table_args__ = {"schema": "identity"}  # noqa: RUF012

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True)
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(Uuid())
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("identity.identity_user.id"))
    role_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("identity.role.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class RefreshTokenModel(Base):
    __tablename__ = "refresh_token"
    __table_args__ = {"schema": "identity"}  # noqa: RUF012

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True)
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(Uuid())
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("identity.identity_user.id"))
    token_hash: Mapped[str] = mapped_column(String(128))
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    rotated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    replaced_by_id: Mapped[uuid.UUID | None] = mapped_column(Uuid())
    user_agent: Mapped[str | None] = mapped_column(String(500))
    ip_address: Mapped[str | None] = mapped_column(String(45))


class PasswordResetTokenModel(Base):
    __tablename__ = "password_reset_token"
    __table_args__ = {"schema": "identity"}  # noqa: RUF012

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True)
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(Uuid())
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("identity.identity_user.id"))
    token_hash: Mapped[str] = mapped_column(String(128))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
