"""add customers:manage permission

`POST /customers/{id}/approve` and the new `POST /customers/{id}/close`
(R10, ConnectionClosed event) both gate on `require_permission("customers:
manage")` — but no `customers:manage` permission code has ever existed in
`identity.permission`. `4f4645fda65e` seeded `customers:read`/`customers:
update`; `fa52b77ec442` seeded `customers:create`; nothing ever seeded
`customers:manage`. Since a claims-based `require_permission` check denies
whenever the code is simply absent from the caller's `permission_codes`,
`/approve` has been **unconditionally unreachable by every role since it
shipped** — found while wiring the new `/close` endpoint, which would have
been equally dead on arrival with the same code.

Role list: `agency_admin`, `manager` — narrower than `customers:update`
(`agency_admin`, `manager`, `dispatcher`), since both actions this code
gates (approving a customer, closing a connection for good) are more
consequential than a routine profile update and dispatchers don't perform
either in practice.

Backfills `identity.identity_user_permission`, not just `role_permission`
— see `f3c8a56d29e1`'s docstring for why a role-only grant would apply to
nobody who already exists (permission resolution has been per-user only
since `8c221c3e0a91`).

Revision ID: 76aa61425c66
Revises: f3c8a56d29e1
Create Date: 2026-08-19
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "76aa61425c66"
down_revision: str | None = "f3c8a56d29e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ROLES_SQL = "('agency_admin', 'manager')"


def upgrade() -> None:
    op.execute("""
        INSERT INTO identity.permission (code, resource, action)
        VALUES ('customers:manage', 'customers', 'manage')
        ON CONFLICT (code) DO NOTHING
    """)

    op.execute(f"""
        INSERT INTO identity.role_permission (role_id, permission_id)
        SELECT r.id, p.id
        FROM identity.role r
        CROSS JOIN identity.permission p
        WHERE r.code IN {_ROLES_SQL}
          AND p.code = 'customers:manage'
        ON CONFLICT (role_id, permission_id) DO NOTHING
    """)

    # Backfill existing users of those roles — see module docstring.
    op.execute(f"""
        INSERT INTO identity.identity_user_permission (id, user_id, permission_id, created_at)
        SELECT gen_random_uuid(), u.id, p.id, now()
        FROM identity.identity_user u
        JOIN identity.permission p ON p.code = 'customers:manage'
        WHERE u.role IN {_ROLES_SQL}
          AND NOT EXISTS (
              SELECT 1 FROM identity.identity_user_permission existing
              WHERE existing.user_id = u.id AND existing.permission_id = p.id
          )
    """)


def downgrade() -> None:
    op.execute("""
        DELETE FROM identity.identity_user_permission
        WHERE permission_id IN (SELECT id FROM identity.permission WHERE code = 'customers:manage')
    """)
    op.execute("""
        DELETE FROM identity.role_permission
        WHERE permission_id IN (SELECT id FROM identity.permission WHERE code = 'customers:manage')
    """)
    op.execute("DELETE FROM identity.permission WHERE code = 'customers:manage'")
