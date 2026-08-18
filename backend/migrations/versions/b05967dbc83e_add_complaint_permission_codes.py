"""add_complaint_permission_codes

Revision ID: b05967dbc83e
Revises: 4e7fc25f58b3
Create Date: 2026-08-14 15:12:57.515263

"""

from __future__ import annotations

from typing import TYPE_CHECKING

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = 'b05967dbc83e'
down_revision: str | None = '4e7fc25f58b3'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Insert permission code
    op.execute(
        """
        INSERT INTO identity.permission (code, resource, action)
        VALUES (
            'complaints.manage',
            'complaints',
            'manage'
        )
        ON CONFLICT (code) DO NOTHING;
        """
    )

    # 2. Grant to appropriate roles
    op.execute(
        """
        INSERT INTO identity.role_permission (role_id, permission_id)
        SELECT r.id, p.id
        FROM identity.role r
        CROSS JOIN identity.permission p
        WHERE r.code IN ('super_admin', 'agency_admin', 'manager', 'dispatcher', 'customer')
          AND p.code = 'complaints.manage'
        ON CONFLICT (role_id, permission_id) DO NOTHING;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM identity.role_permission
        WHERE permission_id IN (
            SELECT id FROM identity.permission WHERE code IN ('complaints.manage')
        );
        """
    )
    op.execute(
        """
        DELETE FROM identity.permission
        WHERE code IN ('complaints.manage');
        """
    )
