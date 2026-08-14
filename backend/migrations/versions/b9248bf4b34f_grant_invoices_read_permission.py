"""grant invoices:read permission

Revision ID: b9248bf4b34f
Revises: de95b5bcc7de
Create Date: 2026-08-14 11:37:45.000000

"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "b9248bf4b34f"
down_revision: str | None = "0df30969e03e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_IDENTITY_SCHEMA = "identity"
_PERMISSION_CODE = "invoices:read"
_ROLES = ["super_admin", "agency_admin", "manager", "accountant"]


def upgrade() -> None:
    for role_code in _ROLES:
        op.execute(
            sa.text(f"""
                INSERT INTO {_IDENTITY_SCHEMA}.role_permission
                    (id, role_id, permission_id, created_at)
                SELECT gen_random_uuid(), r.id, p.id, now()
                FROM {_IDENTITY_SCHEMA}.role r, {_IDENTITY_SCHEMA}.permission p
                WHERE r.code = :role_code AND p.code = :permission_code
                ON CONFLICT (role_id, permission_id) DO NOTHING
            """).bindparams(role_code=role_code, permission_code=_PERMISSION_CODE)
        )


def downgrade() -> None:
    op.execute(
        sa.text(f"""
            DELETE FROM {_IDENTITY_SCHEMA}.role_permission
            WHERE permission_id IN (
                SELECT id FROM {_IDENTITY_SCHEMA}.permission WHERE code = :permission_code
            )
        """).bindparams(permission_code=_PERMISSION_CODE)
    )
