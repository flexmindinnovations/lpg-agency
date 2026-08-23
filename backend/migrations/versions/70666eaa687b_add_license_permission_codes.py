"""add license permission codes

Revision ID: 70666eaa687b
Revises: 92e48f9bf322
Create Date: 2026-08-22 17:05:00.000000

Two new permission codes for tenant license activation, mirroring
`feature_flags:manage_tenant`/`feature_flags:manage_platform`'s exact
sensitivity split:

- `license:manage_tenant` — activate own tenant's license, manage own
  tenant's linked devices (`agency_admin`)
- `license:manage_platform` — issue/revoke licenses, set plan tier/device
  caps/feature overrides (`super_admin` only, **live-checked** — same
  high-sensitivity pattern `feature_flags:manage_platform` uses)

`GET /license/status` intentionally has no permission code — see
`lpg.application.license.license_status`'s module docstring.

**Backfills `identity.identity_user_permission`, not just `role_permission`.**
Missed on first write of this migration — copied the shape of the older
`b8d4e0a6c2f9_add_administration_permission_codes.py`, which predates the
convention `8c221c3e0a91`/`f3c8a56d29e1` established and documented: since
`8c221c3e0a91`, permission resolution (`issue_tokens` ->
`PermissionRepository.get_permission_codes_for_user`) is per-user only and
never consults `role_permission` at request/login time. A migration that
only inserts into `role_permission` grants the new code to nobody who
already exists — confirmed live: an existing `agency_admin` dev account's
JWT `scope` claim had no `license:manage_tenant` after this migration ran,
so the License nav item it gates never appeared for that account, even
though `role_permission` itself was correct. Same `NOT EXISTS` idempotent
guard `f3c8a56d29e1` uses, for the same reason (no unique constraint on
`(user_id, permission_id)` to lean on instead).
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "70666eaa687b"
down_revision: str | None = "92e48f9bf322"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "identity"

_NEW_PERMISSIONS = [
    "license:manage_tenant",
    "license:manage_platform",
]

_NEW_ROLE_PERMISSION_MATRIX: list[tuple[str, list[str]]] = [
    ("license:manage_tenant", ["agency_admin"]),
    ("license:manage_platform", ["super_admin"]),
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

            # Backfill existing users of that role — see module docstring.
            op.execute(
                sa.text(f"""
                    INSERT INTO {_SCHEMA}.identity_user_permission (id, user_id, permission_id, created_at)
                    SELECT gen_random_uuid(), u.id, :permission_id, now()
                    FROM {_SCHEMA}.identity_user u
                    WHERE u.role = :role_code
                      AND NOT EXISTS (
                          SELECT 1 FROM {_SCHEMA}.identity_user_permission existing
                          WHERE existing.user_id = u.id AND existing.permission_id = :permission_id
                      )
                """).bindparams(permission_id=permission_ids[permission_code], role_code=role_code)
            )


def downgrade() -> None:
    codes_literal = ", ".join(f"'{code}'" for code in _NEW_PERMISSIONS)
    op.execute(f"""
        DELETE FROM {_SCHEMA}.identity_user_permission
        WHERE permission_id IN (
            SELECT id FROM {_SCHEMA}.permission WHERE code IN ({codes_literal})
        )
    """)
    op.execute(f"""
        DELETE FROM {_SCHEMA}.role_permission
        WHERE permission_id IN (
            SELECT id FROM {_SCHEMA}.permission WHERE code IN ({codes_literal})
        )
    """)
    op.execute(f"DELETE FROM {_SCHEMA}.permission WHERE code IN ({codes_literal})")
