"""one linked device per phone per agency, and remember whether it was named

A phone is recognised by its hardware reference (the hashed Android ID / iOS
vendor ID) so reinstalling the app no longer creates a second record
(ADR-072). This migration

- retires older duplicate records of the same phone: for each
  (tenant, app, hardware reference) the most recently seen record stays, the
  others are marked removed and lose the hardware link (their history stays);
- makes (tenant_id, app_type, hardware_ref) unique;
- adds `name_confirmed`: false while the name is the generated
  `device_<ref>` default and the app should still ask for one. Existing
  records count as named.

Revision ID: a9d4c2e7b816
Revises: e4b7a1c9d3f2
Create Date: 2026-11-07 20:00:00.000000

"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "a9d4c2e7b816"
down_revision: str | None = "e4b7a1c9d3f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "platform"
_TABLE = "linked_device"
_INDEX = "uq_linked_device_tenant_app_hardware"


def upgrade() -> None:
    op.add_column(
        _TABLE,
        sa.Column("name_confirmed", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        schema=_SCHEMA,
    )
    # Older duplicates of one phone: keep the latest, retire the rest.
    op.execute(
        f"""
        WITH ranked AS (
            SELECT id,
                   row_number() OVER (
                       PARTITION BY tenant_id, app_type, hardware_ref
                       ORDER BY (status <> 'removed') DESC, last_seen_at DESC, id
                   ) AS position
            FROM {_SCHEMA}.{_TABLE}
            WHERE hardware_ref IS NOT NULL
        )
        UPDATE {_SCHEMA}.{_TABLE} AS device
        SET status = 'removed',
            revoked_at = COALESCE(device.revoked_at, now()),
            status_changed_at = now(),
            hardware_ref = NULL
        FROM ranked
        WHERE device.id = ranked.id AND ranked.position > 1
        """
    )
    op.create_index(
        _INDEX,
        _TABLE,
        ["tenant_id", "app_type", "hardware_ref"],
        unique=True,
        schema=_SCHEMA,
        postgresql_where=sa.text("hardware_ref IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(_INDEX, table_name=_TABLE, schema=_SCHEMA)
    op.drop_column(_TABLE, "name_confirmed", schema=_SCHEMA)
