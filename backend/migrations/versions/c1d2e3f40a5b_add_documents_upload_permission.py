"""add documents:upload permission

The generic `/documents` endpoints (pre-upload + server-side OCR of a scanned
document, shared by customer KYC and driver/vehicle compliance) are gated by a
new `documents:upload` permission. Granted to the same roles that already
manage drivers/vehicles (`a1b2c3d4e5f6_create_delivery_schema`'s
`_MANAGE_ROLES`).

The `compliance_document` table, its RLS policy, and `compliance:verify` land
in a follow-up migration with the rest of the compliance pack.

Revision ID: c1d2e3f40a5b
Revises: b3e1d7a24f90
Create Date: 2026-09-06
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "c1d2e3f40a5b"
down_revision: str | None = "b3e1d7a24f90"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PERMISSION = "documents:upload"
_ROLES_SQL = "('super_admin', 'agency_admin', 'manager', 'dispatcher')"


def upgrade() -> None:
    op.execute(f"""
        INSERT INTO identity.permission (code, resource, action)
        VALUES ('{_PERMISSION}', 'documents', 'upload')
        ON CONFLICT (code) DO NOTHING
    """)

    op.execute(f"""
        INSERT INTO identity.role_permission (role_id, permission_id)
        SELECT r.id, p.id
        FROM identity.role r
        CROSS JOIN identity.permission p
        WHERE r.code IN {_ROLES_SQL}
          AND p.code = '{_PERMISSION}'
        ON CONFLICT (role_id, permission_id) DO NOTHING
    """)

    # Backfill existing users of those roles — a role_permission-only grant
    # applies to nobody who already exists (see c039189dfbdc's docstring).
    op.execute(f"""
        INSERT INTO identity.identity_user_permission (id, user_id, permission_id, created_at)
        SELECT gen_random_uuid(), u.id, p.id, now()
        FROM identity.identity_user u
        JOIN identity.permission p ON p.code = '{_PERMISSION}'
        WHERE u.role IN {_ROLES_SQL}
          AND NOT EXISTS (
              SELECT 1 FROM identity.identity_user_permission existing
              WHERE existing.user_id = u.id AND existing.permission_id = p.id
          )
    """)


def downgrade() -> None:
    op.execute(f"""
        DELETE FROM identity.identity_user_permission
        WHERE permission_id IN (
            SELECT id FROM identity.permission WHERE code = '{_PERMISSION}'
        )
    """)
    op.execute(f"""
        DELETE FROM identity.role_permission
        WHERE permission_id IN (
            SELECT id FROM identity.permission WHERE code = '{_PERMISSION}'
        )
    """)
    op.execute(f"DELETE FROM identity.permission WHERE code = '{_PERMISSION}'")
