"""create_customer_schema

Revision ID: 4f4645fda65e
Revises: b8d4e0a6c2f9
Create Date: 2026-08-10 20:13:23.996155

"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "4f4645fda65e"
down_revision: str | None = "b8d4e0a6c2f9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "customer"


def _standard_columns() -> list[sa.Column]:
    """The audit-column set every table in this codebase carries."""
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.Uuid(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
    ]


def _grant(*, table: str, privileges: str) -> str:
    """Dynamic role-detection grant block."""
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
                    'GRANT {privileges} ON {_SCHEMA}.{table} TO %I', app_role
                );
            END IF;
        END
        $$;
    """


def _enable_rls(table: str) -> None:
    op.execute(f"ALTER TABLE {_SCHEMA}.{table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {_SCHEMA}.{table} FORCE ROW LEVEL SECURITY")
    op.execute(f"""
        CREATE POLICY rls_{_SCHEMA}_{table}_isolation ON {_SCHEMA}.{table}
        USING ({_TENANT_RLS_PREDICATE})
    """)


_TENANT_RLS_PREDICATE = (
    "tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid"
)


def upgrade() -> None:
    # 1. Create schema
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {_SCHEMA}")

    # 2. Create customer.customer table
    op.create_table(
        "customer",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "tenant_id",
            sa.Uuid(),
            sa.ForeignKey("tenant.tenant.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "branch_id",
            sa.Uuid(),
            sa.ForeignKey("tenant.branch.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("consumer_number", sa.String(length=50), nullable=False),
        sa.Column("full_name", sa.String(length=200), nullable=False),
        sa.Column("phone_number", sa.String(length=20), nullable=False),
        sa.Column(
            "customer_type",
            sa.String(length=50),
            nullable=False,
            server_default="domestic",
        ),
        sa.Column(
            "kyc_status",
            sa.String(length=50),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "status",
            sa.String(length=50),
            nullable=False,
            server_default="active",
        ),
        sa.Column(
            "search_vector",
            sa.dialects.postgresql.TSVECTOR(),
            sa.Computed("to_tsvector('english', coalesce(full_name, ''))", persisted=True),
            nullable=True,
        ),
        *_standard_columns(),
        sa.CheckConstraint(
            "customer_type IN ('domestic', 'commercial', 'industrial', 'government')",
            name="chk_customer_customer_type",
        ),
        sa.CheckConstraint(
            "kyc_status IN ('pending', 'verified', 'rejected', 'expired')",
            name="chk_customer_kyc_status",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'inactive', 'blocked', 'closed')",
            name="chk_customer_status",
        ),
        schema=_SCHEMA,
    )

    # Indexes / Unique Constraints for customer.customer
    op.create_index(
        "uq_customer_tenant_consumer_number",
        "customer",
        ["tenant_id", "consumer_number"],
        unique=True,
        schema=_SCHEMA,
    )
    op.create_index(
        "uq_customer_tenant_phone",
        "customer",
        ["tenant_id", "phone_number"],
        unique=True,
        schema=_SCHEMA,
    )
    op.create_index(
        "idx_customer_tenant_phone",
        "customer",
        ["tenant_id", "phone_number"],
        unique=False,
        schema=_SCHEMA,
    )
    op.create_index(
        "idx_customer_search_gin",
        "customer",
        ["search_vector"],
        unique=False,
        postgresql_using="gin",
        schema=_SCHEMA,
    )
    op.create_index(
        "idx_customer_tenant_active",
        "customer",
        ["tenant_id", "status"],
        unique=False,
        postgresql_where=sa.text("is_deleted = false"),
        schema=_SCHEMA,
    )

    # 3. Create customer.customer_address table
    op.create_table(
        "customer_address",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "tenant_id",
            sa.Uuid(),
            sa.ForeignKey("tenant.tenant.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "customer_id",
            sa.Uuid(),
            sa.ForeignKey(f"{_SCHEMA}.customer.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("address_line", sa.Text(), nullable=False),
        sa.Column("latitude", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column("longitude", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        *_standard_columns(),
        schema=_SCHEMA,
    )

    op.create_index(
        "uq_customeraddress_one_primary",
        "customer_address",
        ["customer_id"],
        unique=True,
        postgresql_where=sa.text("is_primary = true AND is_deleted = false"),
        schema=_SCHEMA,
    )

    # 4. Create customer.kyc_document table
    op.create_table(
        "kyc_document",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "tenant_id",
            sa.Uuid(),
            sa.ForeignKey("tenant.tenant.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "customer_id",
            sa.Uuid(),
            sa.ForeignKey(f"{_SCHEMA}.customer.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("doc_type", sa.String(length=50), nullable=False),
        sa.Column("doc_reference", sa.Text(), nullable=False),
        sa.Column(
            "verification_status",
            sa.String(length=50),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "verified_by",
            sa.Uuid(),
            sa.ForeignKey("identity.identity_user.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        *_standard_columns(),
        sa.CheckConstraint(
            "verification_status IN ('pending', 'verified', 'rejected')",
            name="chk_customer_kyc_verification_status",
        ),
        schema=_SCHEMA,
    )

    # 5. Enable RLS
    _enable_rls("customer")
    _enable_rls("customer_address")
    _enable_rls("kyc_document")

    # 6. Apply Grants
    op.execute(_grant(table="customer", privileges="SELECT, INSERT, UPDATE"))
    op.execute(_grant(table="customer_address", privileges="SELECT, INSERT, UPDATE, DELETE"))
    op.execute(_grant(table="kyc_document", privileges="SELECT, INSERT, UPDATE"))

    # 7. Map customers:read and customers:update to roles
    _ID = "identity"
    _READ_ROLES = ["agency_admin", "manager", "dispatcher", "accountant", "driver"]
    _UPDATE_ROLES = ["agency_admin", "manager", "dispatcher"]
    for permission_code, role_codes in (
        ("customers:read", _READ_ROLES),
        ("customers:update", _UPDATE_ROLES),
    ):
        for role_code in role_codes:
            op.execute(
                sa.text(f"""
                    INSERT INTO {_ID}.role_permission (id, role_id, permission_id, created_at)
                    SELECT gen_random_uuid(), r.id, p.id, now()
                    FROM {_ID}.role r, {_ID}.permission p
                    WHERE r.code = :role_code AND p.code = :permission_code
                    ON CONFLICT DO NOTHING
                """).bindparams(role_code=role_code, permission_code=permission_code)
            )


def downgrade() -> None:
    op.execute(
        f"DROP POLICY IF EXISTS rls_{_SCHEMA}_kyc_document_isolation ON {_SCHEMA}.kyc_document"
    )
    op.execute(
        f"DROP POLICY IF EXISTS rls_{_SCHEMA}_customer_address_isolation "
        f"ON {_SCHEMA}.customer_address"
    )
    op.execute(f"DROP POLICY IF EXISTS rls_{_SCHEMA}_customer_isolation ON {_SCHEMA}.customer")

    op.drop_table("kyc_document", schema=_SCHEMA)
    op.drop_table("customer_address", schema=_SCHEMA)
    op.drop_table("customer", schema=_SCHEMA)
