"""create customer.onboarding_draft table + onboarding_drafts:manage permission

A staff user's in-progress Customer Onboarding wizard state — see
`domain/customer/onboarding_draft.py`'s module docstring for why this is a
thin JSON-holding record, not a full aggregate. Owned by `created_by` (the
staff user filling it in), not by a customer — no `Customer` row exists yet
while a draft does.

`onboarding_drafts:manage` is new and distinct from `customers:create`
(unlike most CRUD-adjacent actions, which reuse existing customer
permissions) because a draft holds the same unverified PII a KYC record
does — same reasoning `c9a1e6b4f7d3_add_kyc_permission_codes.py` used to
split `kyc:read`/`kyc:manage` out from `customers:read`/`customers:update`.
Granted to `agency_admin`/`manager` (matching `kyc:manage`) plus `dispatcher`
(matching `customers:create`'s broader front-desk-facing role set, since
running the onboarding wizard at all already requires `customers:create`).

Revision ID: a3f6c8d1b7e5
Revises: 3dd09c061286
Create Date: 2026-08-20
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "a3f6c8d1b7e5"
down_revision: str | None = "3dd09c061286"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "customer"
_TABLE = "onboarding_draft"
_PERMISSION_CODE = "onboarding_drafts:manage"
_ROLES_SQL = "('agency_admin', 'manager', 'dispatcher')"


def _grant(*, privileges: str) -> str:
    return f"""
        DO $$
        DECLARE
            app_role text := CASE current_database()
                WHEN 'lpg_uat' THEN 'lpg_app_uat'
                ELSE 'lpg_app'
            END;
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = app_role) THEN
                EXECUTE format('GRANT USAGE ON SCHEMA {_SCHEMA} TO %I', app_role);
                EXECUTE format(
                    'GRANT {privileges} ON {_SCHEMA}.{_TABLE} TO %I', app_role
                );
            END IF;
        END
        $$;
    """


def upgrade() -> None:
    op.execute(f"""
        CREATE TABLE {_SCHEMA}.{_TABLE} (
            id uuid PRIMARY KEY,
            tenant_id uuid NOT NULL REFERENCES tenant.tenant(id) ON DELETE CASCADE,
            created_by uuid NOT NULL,
            branch_id uuid NULL REFERENCES tenant.branch(id) ON DELETE SET NULL,
            current_step smallint NOT NULL DEFAULT 1,
            registration_data jsonb NOT NULL DEFAULT '{{}}'::jsonb,
            address_data jsonb NOT NULL DEFAULT '{{}}'::jsonb,
            kyc_data jsonb NOT NULL DEFAULT '{{}}'::jsonb,
            kyc_document_blob_ref text NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute(
        f"CREATE INDEX idx_{_SCHEMA}_{_TABLE}_tenant_user "
        f"ON {_SCHEMA}.{_TABLE} (tenant_id, created_by)"
    )

    op.execute(_grant(privileges="SELECT, INSERT, UPDATE, DELETE"))

    op.execute(f"ALTER TABLE {_SCHEMA}.{_TABLE} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {_SCHEMA}.{_TABLE} FORCE ROW LEVEL SECURITY")
    op.execute(f"""
        CREATE POLICY rls_{_SCHEMA}_{_TABLE}_isolation ON {_SCHEMA}.{_TABLE}
        USING (
            tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
        )
    """)

    permission_table = sa.table(
        "permission",
        sa.column("id", sa.Uuid()),
        sa.column("code", sa.String()),
        sa.column("resource", sa.String()),
        sa.column("action", sa.String()),
        schema="identity",
    )
    permission_id = uuid.uuid4()
    op.bulk_insert(
        permission_table,
        [
            {
                "id": permission_id,
                "code": _PERMISSION_CODE,
                "resource": _PERMISSION_CODE.split(":")[0],
                "action": _PERMISSION_CODE.split(":")[1],
            }
        ],
    )

    op.execute(
        sa.text(f"""
            INSERT INTO identity.role_permission (id, role_id, permission_id, created_at)
            SELECT gen_random_uuid(), r.id, :permission_id, now()
            FROM identity.role r
            WHERE r.code IN {_ROLES_SQL}
        """).bindparams(permission_id=permission_id)
    )

    # Backfill existing users of those roles — permission resolution is
    # per-user, not just per-role, see c039189dfbdc's identical note.
    op.execute(
        sa.text(f"""
            INSERT INTO identity.identity_user_permission (id, user_id, permission_id, created_at)
            SELECT gen_random_uuid(), u.id, :permission_id, now()
            FROM identity.identity_user u
            WHERE u.role IN {_ROLES_SQL}
              AND NOT EXISTS (
                  SELECT 1 FROM identity.identity_user_permission existing
                  WHERE existing.user_id = u.id AND existing.permission_id = :permission_id
              )
        """).bindparams(permission_id=permission_id)
    )


def downgrade() -> None:
    op.execute(f"""
        DELETE FROM identity.identity_user_permission
        WHERE permission_id IN (
            SELECT id FROM identity.permission WHERE code = '{_PERMISSION_CODE}'
        )
    """)
    op.execute(f"""
        DELETE FROM identity.role_permission
        WHERE permission_id IN (
            SELECT id FROM identity.permission WHERE code = '{_PERMISSION_CODE}'
        )
    """)
    op.execute(f"DELETE FROM identity.permission WHERE code = '{_PERMISSION_CODE}'")

    op.execute(
        f"DROP POLICY IF EXISTS rls_{_SCHEMA}_{_TABLE}_isolation ON {_SCHEMA}.{_TABLE}"
    )
    op.execute(f"ALTER TABLE {_SCHEMA}.{_TABLE} NO FORCE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {_SCHEMA}.{_TABLE} DISABLE ROW LEVEL SECURITY")
    op.execute(f"DROP TABLE IF EXISTS {_SCHEMA}.{_TABLE}")
