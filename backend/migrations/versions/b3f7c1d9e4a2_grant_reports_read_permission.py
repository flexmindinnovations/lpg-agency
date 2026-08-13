"""grant reports:read to staff roles

Revision ID: b3f7c1d9e4a2
Revises: 4f8b2d6a9c1e
Create Date: 2026-08-11 20:00:00.000000

`reports:read` was seeded as a permission *code* in `fa52b77ec442` (Phase 6's
illustrative catalog) but never granted to any role — that migration's own
9-row matrix was explicitly "illustrative, not exhaustive", with further
grants arriving as each business phase actually builds an endpoint gated by
that code. The dashboard summary endpoint is the first such endpoint, so
this migration closes the gap: `reports:read` -> every staff role that uses
the Dashboard (`driver`/`customer` use the mobile apps, not this surface).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "b3f7c1d9e4a2"
down_revision: str | None = "4f8b2d6a9c1e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_IDENTITY_SCHEMA = "identity"
_PERMISSION_CODE = "reports:read"
_ROLES = ["super_admin", "agency_admin", "manager", "warehouse_staff", "dispatcher", "accountant"]


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
