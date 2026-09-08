"""widen delivery.compliance_document owner types to warehouse/tenant

Compliance Calendar (ADR-044) — a Tier-0 licence registry (PESO Form F per
warehouse, the tenant's own insurance policy) built as a thin extension of
the existing driver/vehicle compliance-document system (D24/ADR-038). The
repository, application use cases, and the nightly expiry cron are already
generic over `owner_type` — only the DB CHECK constraint needs widening.

Also adds `compliance:manage`/`compliance:read` — new, narrower permissions
for the warehouse/tenant document endpoints, granted to the same role set as
the existing `compliance:verify` (`super_admin, agency_admin, manager`).
The existing generic replace/verify endpoints (`drivers:manage`/
`compliance:verify`) are left untouched — narrowing those shared gates risks
locking out current driver/vehicle-page callers (`dispatcher` also holds
`drivers:manage`, `warehouse_staff`/`accountant`/`driver` also hold
`drivers:read`).

Revision ID: a7c4e9f21b8d
Revises: f4a8c2d9e6b1
Create Date: 2026-09-08
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "a7c4e9f21b8d"
down_revision: str | None = "f4a8c2d9e6b1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "delivery"
_TABLE = "compliance_document"
_CHECK_NAME = "compliance_document_owner_type_check"
_OLD_OWNER_TYPES = "('driver', 'vehicle')"
_NEW_OWNER_TYPES = "('driver', 'vehicle', 'warehouse', 'tenant')"

_NEW_PERMISSIONS = [
    ("compliance:manage", "compliance", "manage"),
    ("compliance:read", "compliance", "read"),
]
_GRANT_ROLES_SQL = "('super_admin', 'agency_admin', 'manager')"


def upgrade() -> None:
    op.execute(
        f"ALTER TABLE {_SCHEMA}.{_TABLE} DROP CONSTRAINT {_CHECK_NAME}"
    )
    op.execute(
        f"ALTER TABLE {_SCHEMA}.{_TABLE} ADD CONSTRAINT {_CHECK_NAME} "
        f"CHECK (owner_type IN {_NEW_OWNER_TYPES})"
    )

    for code, resource, action in _NEW_PERMISSIONS:
        op.execute(f"""
            INSERT INTO identity.permission (code, resource, action)
            VALUES ('{code}', '{resource}', '{action}')
            ON CONFLICT (code) DO NOTHING
        """)
        op.execute(f"""
            INSERT INTO identity.role_permission (role_id, permission_id)
            SELECT r.id, p.id
            FROM identity.role r
            CROSS JOIN identity.permission p
            WHERE r.code IN {_GRANT_ROLES_SQL}
              AND p.code = '{code}'
            ON CONFLICT (role_id, permission_id) DO NOTHING
        """)
        op.execute(f"""
            INSERT INTO identity.identity_user_permission (id, user_id, permission_id, created_at)
            SELECT gen_random_uuid(), u.id, p.id, now()
            FROM identity.identity_user u
            JOIN identity.permission p ON p.code = '{code}'
            WHERE u.role IN {_GRANT_ROLES_SQL}
              AND NOT EXISTS (
                  SELECT 1 FROM identity.identity_user_permission existing
                  WHERE existing.user_id = u.id AND existing.permission_id = p.id
              )
        """)


def downgrade() -> None:
    for code, _resource, _action in _NEW_PERMISSIONS:
        op.execute(f"""
            DELETE FROM identity.identity_user_permission
            WHERE permission_id IN (
                SELECT id FROM identity.permission WHERE code = '{code}'
            )
        """)
        op.execute(f"""
            DELETE FROM identity.role_permission
            WHERE permission_id IN (
                SELECT id FROM identity.permission WHERE code = '{code}'
            )
        """)
        op.execute(f"DELETE FROM identity.permission WHERE code = '{code}'")

    op.execute(
        f"ALTER TABLE {_SCHEMA}.{_TABLE} DROP CONSTRAINT {_CHECK_NAME}"
    )
    op.execute(
        f"ALTER TABLE {_SCHEMA}.{_TABLE} ADD CONSTRAINT {_CHECK_NAME} "
        f"CHECK (owner_type IN {_OLD_OWNER_TYPES})"
    )
