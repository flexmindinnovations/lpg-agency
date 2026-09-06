"""create delivery.compliance_document table

Storage for the driver/vehicle compliance pack — a statutory document
(driving licence, RC, insurance, fitness, PUC, PESO transport licence, TREM
card, training certificate) held against a driver or vehicle. Polymorphic
owner (`owner_type` + `owner_id`), no FK on `owner_id`.

Rows are mutable (verify status, replace details, cron's expiry-notified
timestamp) so the app role keeps UPDATE — unlike the append-only
`cash_handover`.

Also adds `compliance:verify` (the manual verify/reject action), granted to
`super_admin, agency_admin, manager`.

Revision ID: d2e3f4051a6c
Revises: c1d2e3f40a5b
Create Date: 2026-09-06
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "d2e3f4051a6c"
down_revision: str | None = "c1d2e3f40a5b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "delivery"
_TABLE = "compliance_document"
_PERMISSION = "compliance:verify"
_VERIFY_ROLES_SQL = "('super_admin', 'agency_admin', 'manager')"


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
                EXECUTE format('GRANT {privileges} ON {_SCHEMA}.{_TABLE} TO %I', app_role);
            END IF;
        END
        $$;
    """


def upgrade() -> None:
    op.execute(f"""
        CREATE TABLE {_SCHEMA}.{_TABLE} (
            id uuid PRIMARY KEY,
            tenant_id uuid NOT NULL REFERENCES tenant.tenant(id) ON DELETE CASCADE,
            owner_type varchar(20) NOT NULL CHECK (owner_type IN ('driver', 'vehicle')),
            owner_id uuid NOT NULL,
            doc_type varchar(50) NOT NULL,
            document_number varchar NOT NULL,
            file_ref varchar NOT NULL,
            issue_date date,
            expiry_date date,
            verification_status varchar(20) NOT NULL DEFAULT 'pending'
                CHECK (verification_status IN ('pending', 'verified', 'rejected')),
            rejection_reason varchar,
            verified_by uuid REFERENCES identity.identity_user(id) ON DELETE SET NULL,
            verified_at timestamptz,
            last_expiry_notified_at timestamptz,
            created_at timestamptz NOT NULL DEFAULT now(),
            created_by uuid,
            updated_at timestamptz NOT NULL DEFAULT now(),
            updated_by uuid,
            is_deleted boolean NOT NULL DEFAULT false,
            deleted_at timestamptz,
            deleted_by uuid,
            version integer NOT NULL DEFAULT 1
        )
    """)
    op.execute(
        f"CREATE INDEX idx_{_SCHEMA}_{_TABLE}_owner "
        f"ON {_SCHEMA}.{_TABLE} (owner_type, owner_id) WHERE NOT is_deleted"
    )
    op.execute(
        f"CREATE INDEX idx_{_SCHEMA}_{_TABLE}_expiry "
        f"ON {_SCHEMA}.{_TABLE} (expiry_date) WHERE NOT is_deleted"
    )

    op.execute(_grant(privileges="SELECT, INSERT, UPDATE"))

    op.execute(f"ALTER TABLE {_SCHEMA}.{_TABLE} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {_SCHEMA}.{_TABLE} FORCE ROW LEVEL SECURITY")
    op.execute(f"""
        CREATE POLICY rls_{_SCHEMA}_{_TABLE}_isolation ON {_SCHEMA}.{_TABLE}
        USING (
            tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
        )
    """)

    op.execute(f"""
        INSERT INTO identity.permission (code, resource, action)
        VALUES ('{_PERMISSION}', 'compliance', 'verify')
        ON CONFLICT (code) DO NOTHING
    """)
    op.execute(f"""
        INSERT INTO identity.role_permission (role_id, permission_id)
        SELECT r.id, p.id
        FROM identity.role r
        CROSS JOIN identity.permission p
        WHERE r.code IN {_VERIFY_ROLES_SQL}
          AND p.code = '{_PERMISSION}'
        ON CONFLICT (role_id, permission_id) DO NOTHING
    """)
    op.execute(f"""
        INSERT INTO identity.identity_user_permission (id, user_id, permission_id, created_at)
        SELECT gen_random_uuid(), u.id, p.id, now()
        FROM identity.identity_user u
        JOIN identity.permission p ON p.code = '{_PERMISSION}'
        WHERE u.role IN {_VERIFY_ROLES_SQL}
          AND NOT EXISTS (
              SELECT 1 FROM identity.identity_user_permission existing
              WHERE existing.user_id = u.id AND existing.permission_id = p.id
          )
    """)


def downgrade() -> None:
    op.execute(f"""
        DELETE FROM identity.identity_user_permission
        WHERE permission_id IN (
            SELECT id FROM identity.permission WHERE code = '{_PERMISSION}'
        )
    """)
    op.execute(f"""
        DELETE FROM identity.role_permission
        WHERE permission_id IN (
            SELECT id FROM identity.permission WHERE code = '{_PERMISSION}'
        )
    """)
    op.execute(f"DELETE FROM identity.permission WHERE code = '{_PERMISSION}'")

    op.execute(f"DROP POLICY IF EXISTS rls_{_SCHEMA}_{_TABLE}_isolation ON {_SCHEMA}.{_TABLE}")
    op.execute(f"ALTER TABLE {_SCHEMA}.{_TABLE} NO FORCE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {_SCHEMA}.{_TABLE} DISABLE ROW LEVEL SECURITY")
    op.execute(f"DROP TABLE IF EXISTS {_SCHEMA}.{_TABLE}")
