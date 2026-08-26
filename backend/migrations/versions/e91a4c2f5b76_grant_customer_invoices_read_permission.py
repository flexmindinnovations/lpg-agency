"""grant customer role invoices:read permission

`invoices:read` was granted only to `super_admin, agency_admin, manager,
accountant` (`b9248bf4b34f_grant_invoices_read_permission.py`) -- the
`customer` role has none, so a customer can't view their own invoices
today. The router now also enforces ownership scoping for a `customer`
principal (`invoice.py`'s `list_invoices`/`get_invoice`, mirroring
`order.py`'s `_resolve_scope` pattern), so this grant alone doesn't widen
what a customer can see beyond their own invoices.

Revision ID: e91a4c2f5b76
Revises: b7c3f9a1d284
Create Date: 2026-08-26
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "e91a4c2f5b76"
down_revision: str | None = "b7c3f9a1d284"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ROLES_SQL = "('customer')"


def upgrade() -> None:
    op.execute(f"""
        INSERT INTO identity.role_permission (role_id, permission_id)
        SELECT r.id, p.id
        FROM identity.role r
        CROSS JOIN identity.permission p
        WHERE r.code IN {_ROLES_SQL}
          AND p.code = 'invoices:read'
        ON CONFLICT (role_id, permission_id) DO NOTHING
    """)

    op.execute(f"""
        INSERT INTO identity.identity_user_permission (id, user_id, permission_id, created_at)
        SELECT gen_random_uuid(), u.id, p.id, now()
        FROM identity.identity_user u
        JOIN identity.permission p ON p.code = 'invoices:read'
        WHERE u.role IN {_ROLES_SQL}
          AND NOT EXISTS (
              SELECT 1 FROM identity.identity_user_permission existing
              WHERE existing.user_id = u.id AND existing.permission_id = p.id
          )
    """)


def downgrade() -> None:
    op.execute(f"""
        DELETE FROM identity.identity_user_permission
        WHERE permission_id IN (SELECT id FROM identity.permission WHERE code = 'invoices:read')
          AND user_id IN (SELECT id FROM identity.identity_user WHERE role IN {_ROLES_SQL})
    """)
    op.execute(f"""
        DELETE FROM identity.role_permission
        WHERE permission_id IN (SELECT id FROM identity.permission WHERE code = 'invoices:read')
          AND role_id IN (SELECT id FROM identity.role WHERE code IN {_ROLES_SQL})
    """)
