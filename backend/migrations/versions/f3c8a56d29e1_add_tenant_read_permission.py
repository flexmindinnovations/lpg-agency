"""add tenant:read permission

`GET /api/v1/admin/tenant` (`routers/admin.py::get_tenant`) had no permission
dependency at all — only `Depends(get_current_principal)`, i.e.
"authenticated" — while every sibling endpoint in the same router requires
one (`rename_tenant` requires `tenant:configure`). A seeded `driver` could
call it and get `200`; `test_a_driver_is_denied_admin_access` caught this
expecting `403`. No `tenant:read` code existed to gate it with. Confirmed no
frontend feature currently calls this endpoint (`AdminTenantService.getTenant`
has zero callers outside the generated client), so gating it narrows nothing
a real UI depends on today.

Role list mirrors `a907e81bc74c`'s grant for `users:read` — the one existing
precedent in this codebase for a comparable "basic informational read" staff
permission — rather than inventing a new one: `super_admin`, `agency_admin`,
`manager`, `dispatcher`. Deliberately excludes `warehouse_staff`, `accountant`,
`driver`, `customer`, matching what the test asserts and keeping this endpoint
no more broadly readable than the nearest existing analogue.

**Backfills `identity.identity_user_permission`, not just `role_permission`.**
This is the exact gap `b4d19e7c3a52` (harden employee grants) and `R11`
(`identity.py::SqlAlchemyStaffUserRepository.add`) both closed for other
reasons: since `8c221c3e0a91`, permission resolution is per-user only —
`has_permission` never consults `role_permission` at request time. A migration
that only inserts into `role_permission` grants the new code to nobody who
already exists; it would apply solely to users created after this migration
runs. The `NOT EXISTS` guard matches `8c221c3e0a91`'s own idempotent backfill
so a re-run (or running against a database where some of these users already
somehow hold the code) does not duplicate rows — there is no unique
constraint on `(user_id, permission_id)` to lean on instead.

Revision ID: f3c8a56d29e1
Revises: e2a91c4f7b58
Create Date: 2026-08-18
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "f3c8a56d29e1"
down_revision: str | None = "e2a91c4f7b58"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ROLES_SQL = "('super_admin', 'agency_admin', 'manager', 'dispatcher')"


def upgrade() -> None:
    op.execute("""
        INSERT INTO identity.permission (code, resource, action)
        VALUES ('tenant:read', 'tenant', 'read')
        ON CONFLICT (code) DO NOTHING
    """)

    op.execute(f"""
        INSERT INTO identity.role_permission (role_id, permission_id)
        SELECT r.id, p.id
        FROM identity.role r
        CROSS JOIN identity.permission p
        WHERE r.code IN {_ROLES_SQL}
          AND p.code = 'tenant:read'
        ON CONFLICT (role_id, permission_id) DO NOTHING
    """)

    # Backfill existing users of those roles — see module docstring.
    op.execute(f"""
        INSERT INTO identity.identity_user_permission (id, user_id, permission_id, created_at)
        SELECT gen_random_uuid(), u.id, p.id, now()
        FROM identity.identity_user u
        JOIN identity.permission p ON p.code = 'tenant:read'
        WHERE u.role IN {_ROLES_SQL}
          AND NOT EXISTS (
              SELECT 1 FROM identity.identity_user_permission existing
              WHERE existing.user_id = u.id AND existing.permission_id = p.id
          )
    """)


def downgrade() -> None:
    op.execute("""
        DELETE FROM identity.identity_user_permission
        WHERE permission_id IN (SELECT id FROM identity.permission WHERE code = 'tenant:read')
    """)
    op.execute("""
        DELETE FROM identity.role_permission
        WHERE permission_id IN (SELECT id FROM identity.permission WHERE code = 'tenant:read')
    """)
    op.execute("DELETE FROM identity.permission WHERE code = 'tenant:read'")
