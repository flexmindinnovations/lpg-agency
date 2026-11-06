"""add approval state and phone details to platform.linked_device

Device registration and access control (ADR-071). `platform.linked_device`
already existed (licence module) but nothing ever wrote to it. It now holds
one row per phone running the Driver or Admin app, with an approval state
(`pending`, `approved`, `blocked`, `removed`), what the app reports about the
phone, who last signed in on it, and an admin-typed asset note.

The table is already a normal RLS-scoped tenant table (`92e48f9bf322`), so no
policy changes here; the new columns inherit its `tenant_id` isolation.

`device_identifier` now holds the SHA-256 of the app's random install ID and
`hardware_ref` the SHA-256 of the Android ID / iOS vendor ID — never the plain
values. Existing rows (there should be none in practice) keep whatever they
hold and are treated as approved, or as removed when they were revoked, so
nothing changes for them.

Revision ID: c4e8a1f7d305
Revises: f2b6d9a41c73
Create Date: 2026-11-05
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "c4e8a1f7d305"
down_revision: str | None = "f2b6d9a41c73"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "platform"
_TABLE = "linked_device"
_STATUS_CHECK = "ck_linked_device_status"


def upgrade() -> None:
    op.add_column(
        _TABLE,
        sa.Column("status", sa.String(length=20), nullable=False, server_default="approved"),
        schema=_SCHEMA,
    )
    op.add_column(_TABLE, sa.Column("manufacturer", sa.String(length=100)), schema=_SCHEMA)
    op.add_column(_TABLE, sa.Column("model", sa.String(length=100)), schema=_SCHEMA)
    op.add_column(_TABLE, sa.Column("os_version", sa.String(length=50)), schema=_SCHEMA)
    op.add_column(_TABLE, sa.Column("app_version", sa.String(length=50)), schema=_SCHEMA)
    op.add_column(_TABLE, sa.Column("platform", sa.String(length=20)), schema=_SCHEMA)
    op.add_column(_TABLE, sa.Column("hardware_ref", sa.String(length=64)), schema=_SCHEMA)
    op.add_column(_TABLE, sa.Column("asset_note", sa.String(length=64)), schema=_SCHEMA)
    op.add_column(_TABLE, sa.Column("last_user_id", sa.Uuid()), schema=_SCHEMA)
    op.add_column(_TABLE, sa.Column("last_user_name", sa.String(length=200)), schema=_SCHEMA)
    op.add_column(
        _TABLE, sa.Column("status_changed_at", sa.DateTime(timezone=True)), schema=_SCHEMA
    )
    op.add_column(_TABLE, sa.Column("status_changed_by", sa.Uuid()), schema=_SCHEMA)

    op.execute(f"UPDATE {_SCHEMA}.{_TABLE} SET status = 'removed' WHERE revoked_at IS NOT NULL")
    op.execute(
        f"UPDATE {_SCHEMA}.{_TABLE} SET status_changed_at = COALESCE(revoked_at, registered_at)"
    )
    # New rows always state their status explicitly; no silent default.
    op.alter_column(_TABLE, "status", server_default=None, schema=_SCHEMA)
    op.create_check_constraint(
        _STATUS_CHECK,
        _TABLE,
        "status IN ('pending', 'approved', 'blocked', 'removed')",
        schema=_SCHEMA,
    )
    op.create_index(
        "idx_linked_device_tenant_status",
        _TABLE,
        ["tenant_id", "status"],
        schema=_SCHEMA,
    )


def downgrade() -> None:
    op.drop_index("idx_linked_device_tenant_status", table_name=_TABLE, schema=_SCHEMA)
    op.drop_constraint(_STATUS_CHECK, _TABLE, schema=_SCHEMA, type_="check")
    for column in (
        "status_changed_by",
        "status_changed_at",
        "last_user_name",
        "last_user_id",
        "asset_note",
        "hardware_ref",
        "platform",
        "app_version",
        "os_version",
        "model",
        "manufacturer",
        "status",
    ):
        op.drop_column(_TABLE, column, schema=_SCHEMA)
