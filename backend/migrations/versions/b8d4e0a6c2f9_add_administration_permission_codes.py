"""add Phase 7 administration permission codes

Revision ID: b8d4e0a6c2f9
Revises: a7c3e9f5b1d8
Create Date: 2026-08-10 18:30:00.000000

Additive only — existing rows in `identity.permission`/`identity.role_permission`
are never edited in place (established by `fa52b77ec442`'s own seed data).
Four new permission codes for Phase 7's admin surface:

- `users:manage` — invite/deactivate/reassign-role for staff accounts (`agency_admin`)
- `feature_flags:manage_tenant` — toggle tenant-level flag overrides (`agency_admin`)
- `feature_flags:manage_platform` — create/edit platform flags, rollout %,
  scheduling (`super_admin` only, **live-checked** — same high-sensitivity
  pattern `reconciliation:approve` uses)
- `audit:read` — view the audit log (`agency_admin`, `manager`)

Existing rows are looked up by `code`/`role.code` via `INSERT ... SELECT`
rather than pre-generated UUIDs — `fa52b77ec442`'s role/permission UUIDs are
randomly generated at that migration's own run time, unknown here.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "b8d4e0a6c2f9"
down_revision: str | None = "a7c3e9f5b1d8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "identity"

_NEW_PERMISSIONS = [
    "users:manage",
    "feature_flags:manage_tenant",
    "feature_flags:manage_platform",
    "audit:read",
]

_NEW_ROLE_PERMISSION_MATRIX: list[tuple[str, list[str]]] = [
    ("users:manage", ["agency_admin"]),
    ("feature_flags:manage_tenant", ["agency_admin"]),
    ("feature_flags:manage_platform", ["super_admin"]),
    ("audit:read", ["agency_admin", "manager"]),
]


def upgrade() -> None:
    permission_table = sa.table(
        "permission",
        sa.column("id", sa.Uuid()),
        sa.column("code", sa.String()),
        sa.column("resource", sa.String()),
        sa.column("action", sa.String()),
        schema=_SCHEMA,
    )
    permission_ids = {code: uuid.uuid4() for code in _NEW_PERMISSIONS}
    op.bulk_insert(
        permission_table,
        [
            {
                "id": permission_ids[code],
                "code": code,
                "resource": code.split(":")[0],
                "action": code.split(":")[1],
            }
            for code in _NEW_PERMISSIONS
        ],
    )

    # role_permission rows reference roles by code via INSERT ... SELECT —
    # fa52b77ec442's role UUIDs are randomly generated at that migration's
    # own run time, not knowable here.
    for permission_code, role_codes in _NEW_ROLE_PERMISSION_MATRIX:
        for role_code in role_codes:
            op.execute(
                sa.text(f"""
                    INSERT INTO {_SCHEMA}.role_permission (id, role_id, permission_id, created_at)
                    SELECT gen_random_uuid(), r.id, :permission_id, now()
                    FROM {_SCHEMA}.role r
                    WHERE r.code = :role_code
                """).bindparams(permission_id=permission_ids[permission_code], role_code=role_code)
            )


def downgrade() -> None:
    codes_literal = ", ".join(f"'{code}'" for code in _NEW_PERMISSIONS)
    op.execute(f"""
        DELETE FROM {_SCHEMA}.role_permission
        WHERE permission_id IN (
            SELECT id FROM {_SCHEMA}.permission WHERE code IN ({codes_literal})
        )
    """)
    op.execute(f"DELETE FROM {_SCHEMA}.permission WHERE code IN ({codes_literal})")
