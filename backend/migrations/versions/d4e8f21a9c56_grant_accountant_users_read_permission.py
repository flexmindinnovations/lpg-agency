"""grant accountant users:read permission

`GET /employees` (and `GET /employees/{id}`) gate on `require_permission(
"users:read")` (`api/v1/routers/employee.py`). `a907e81bc74c` granted this
code to `super_admin`/`agency_admin`/`manager`/`dispatcher` but left
`accountant` out — yet `accountant` already holds `drivers:read`/
`vehicles:read` (`a1b2c3d4e5f6`), so an accountant can open the Drivers/
Vehicles pages but every employee-code lookup those pages make 403s,
leaving the Employee Code column permanently showing the raw
`employee_id` UUID for that role (not a timing issue — confirmed live,
reproducible every time, no permission to ever resolve it). The employee
code itself isn't sensitive, and every other role that can view a driver
record can already resolve it, so this looks like an oversight in
`a907e81bc74c` rather than a deliberate restriction.

Also backfills `identity.identity_user_permission` for existing
accountant users — `a907e81bc74c` itself skipped this step (only
`role_permission`), which is why it silently didn't apply to any
already-existing manager/dispatcher account either; permission resolution
has been per-user only since `8c221c3e0a91` (see `76aa61425c66`'s
docstring for the same reasoning).

Revision ID: d4e8f21a9c56
Revises: 63c55035ebbb
Create Date: 2026-08-25
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "d4e8f21a9c56"
down_revision: str | None = "63c55035ebbb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ROLES_SQL = "('accountant')"


def upgrade() -> None:
    op.execute(f"""
        INSERT INTO identity.role_permission (role_id, permission_id)
        SELECT r.id, p.id
        FROM identity.role r
        CROSS JOIN identity.permission p
        WHERE r.code IN {_ROLES_SQL}
          AND p.code = 'users:read'
        ON CONFLICT (role_id, permission_id) DO NOTHING
    """)

    # Backfill existing accountant users — see module docstring.
    op.execute(f"""
        INSERT INTO identity.identity_user_permission (id, user_id, permission_id, created_at)
        SELECT gen_random_uuid(), u.id, p.id, now()
        FROM identity.identity_user u
        JOIN identity.permission p ON p.code = 'users:read'
        WHERE u.role IN {_ROLES_SQL}
          AND NOT EXISTS (
              SELECT 1 FROM identity.identity_user_permission existing
              WHERE existing.user_id = u.id AND existing.permission_id = p.id
          )
    """)


def downgrade() -> None:
    op.execute(f"""
        DELETE FROM identity.identity_user_permission
        WHERE permission_id IN (SELECT id FROM identity.permission WHERE code = 'users:read')
          AND user_id IN (SELECT id FROM identity.identity_user WHERE role IN {_ROLES_SQL})
    """)
    op.execute(f"""
        DELETE FROM identity.role_permission
        WHERE permission_id IN (SELECT id FROM identity.permission WHERE code = 'users:read')
          AND role_id IN (SELECT id FROM identity.role WHERE code IN {_ROLES_SQL})
    """)
