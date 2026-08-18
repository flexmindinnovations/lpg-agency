"""add_users_read_permission

Revision ID: a907e81bc74c
Revises: 6feb4eae14a5
Create Date: 2026-08-15 21:31:05.579084

"""

from __future__ import annotations

from typing import TYPE_CHECKING

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = 'a907e81bc74c'
down_revision: str | None = '6feb4eae14a5'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Insert permission code
    op.execute(
        """
        INSERT INTO identity.permission (code, resource, action)
        VALUES (
            'users:read',
            'users',
            'read'
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
        WHERE r.code IN ('super_admin', 'agency_admin', 'manager', 'dispatcher')
          AND p.code = 'users:read'
        ON CONFLICT (role_id, permission_id) DO NOTHING;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM identity.role_permission
        WHERE permission_id IN (
            SELECT id FROM identity.permission WHERE code IN ('users:read')
        );
        """
    )
    op.execute(
        """
        DELETE FROM identity.permission
        WHERE code IN ('users:read');
        """
    )
