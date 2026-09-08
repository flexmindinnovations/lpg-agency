"""grant tdt:read permission

Revision ID: c7f4a2e9b6d1
Revises: a4c79f4e701f
Create Date: 2026-09-08 06:00:00.000000

TDT (Targeted Delivery Time) star rating (`planning/features/
20-regulatory-compliance` subsystem 2) — a new permission code, `tdt:read`,
gating the two read-only endpoints added alongside this migration
(`GET /tdt-rating/quarterly`, `GET /tdt-rating/live-projection`). Unlike
`weighment:manage`/`weighment:record` (seeded in `d8b300ef303f` alongside
the `compliance.scale` table), TDT rating adds no new table — it reads
`orders.order_status_history`/`orders.order`, both already RLS-protected —
so this migration is permission-seeding only, no schema change.

Only one code, no `tdt:configure` — the band/fine-schedule reference data
is written through the existing `tenant:configure`-gated
`POST /admin/tenant-configuration` endpoint (`domain.tenant.
tenant_configuration.RECOGNIZED_CONFIG_KEYS`'s `tdt_star_rating_bands`/
`tdt_fine_schedule`), not a dedicated endpoint.

Granted to operational/management roles who can act on the rating —
`agency_admin`, `manager`, `dispatcher` — not `warehouse_staff` (goods
receipt/load-out, not delivery-timing) or `accountant` (billing, not
dispatch). This role list is an app-permission design choice, not itself
an MDG requirement — unlike the star-band thresholds and fine percentages,
which the source plan is explicit must never be hardcoded, who gets to
*view* the computed rating is ordinary RBAC and can be widened later with
a follow-up grant if needed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "c7f4a2e9b6d1"
down_revision: str | None = "a4c79f4e701f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_IDENTITY_SCHEMA = "identity"
_PERMISSION_CODE = "tdt:read"
_ROLES = ("super_admin", "agency_admin", "manager", "dispatcher")


def _grant_permission_to_roles(permission_code: str, role_codes: tuple[str, ...]) -> None:
    roles_sql = "(" + ", ".join(f"'{r}'" for r in role_codes) + ")"
    op.execute(f"""
        INSERT INTO {_IDENTITY_SCHEMA}.role_permission (role_id, permission_id)
        SELECT r.id, p.id
        FROM {_IDENTITY_SCHEMA}.role r
        CROSS JOIN {_IDENTITY_SCHEMA}.permission p
        WHERE r.code IN {roles_sql}
          AND p.code = '{permission_code}'
        ON CONFLICT (role_id, permission_id) DO NOTHING
    """)
    op.execute(f"""
        INSERT INTO {_IDENTITY_SCHEMA}.identity_user_permission
            (id, user_id, permission_id, created_at)
        SELECT gen_random_uuid(), u.id, p.id, now()
        FROM {_IDENTITY_SCHEMA}.identity_user u
        JOIN {_IDENTITY_SCHEMA}.permission p ON p.code = '{permission_code}'
        WHERE u.role IN {roles_sql}
          AND NOT EXISTS (
              SELECT 1 FROM {_IDENTITY_SCHEMA}.identity_user_permission existing
              WHERE existing.user_id = u.id AND existing.permission_id = p.id
          )
    """)


def upgrade() -> None:
    op.execute(f"""
        INSERT INTO {_IDENTITY_SCHEMA}.permission (code, resource, action)
        VALUES ('{_PERMISSION_CODE}', 'tdt', 'read')
        ON CONFLICT (code) DO NOTHING
    """)
    _grant_permission_to_roles(_PERMISSION_CODE, _ROLES)


def downgrade() -> None:
    op.execute(f"""
        DELETE FROM {_IDENTITY_SCHEMA}.identity_user_permission
        WHERE permission_id IN (
            SELECT id FROM {_IDENTITY_SCHEMA}.permission WHERE code = '{_PERMISSION_CODE}'
        )
    """)
    op.execute(f"""
        DELETE FROM {_IDENTITY_SCHEMA}.role_permission
        WHERE permission_id IN (
            SELECT id FROM {_IDENTITY_SCHEMA}.permission WHERE code = '{_PERMISSION_CODE}'
        )
    """)
    op.execute(f"""
        DELETE FROM {_IDENTITY_SCHEMA}.permission WHERE code = '{_PERMISSION_CODE}'
    """)
