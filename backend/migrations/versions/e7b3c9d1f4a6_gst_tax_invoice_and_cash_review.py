"""GST tax invoices, payment references and cash handover review

QA findings DA-06/DO-15/CA-15, DA-13, DA-07/DO-16, DA-31 and DA-33.

* `tenant.cylinder_type` gains `hsn_code` and `gst_rate_percent`. GST is
  configured per cylinder type; invoice generation refuses (and holds the
  invoice) when neither the cylinder type nor the legacy tenant-wide
  `gst_rate_percent` configuration supplies a rate, so tax is never silently
  0%. Existing cylinder types get HSN 27111900 (every cylinder type an LPG
  agency sells is LPG, HSN heading 2711 per `docs/research/
  feature-gap-analysis.md` R16) but **no rate**: the 5% / 18% split depends
  on how the agency classifies each type, which a migration cannot know.
* `tenant.tenant` gains the agency's GST business profile (legal name,
  GSTIN, address, state code, pincode, phone) that a tax invoice prints as
  the supplier.
* `accounting.invoice` records the supplier state, place of supply and
  customer GSTIN it was issued with (CGST+SGST vs IGST is decided from
  them). `accounting.invoice_line` records the HSN, rate, kind (`supply` or
  `cancellation_charge`) and description it was taxed with. Existing lines
  get their effective rate back-computed from tax/subtotal and HSN
  27111900; existing invoices are not re-taxed.
* `accounting.payment` gains `reference` (cheque number, UTR) and accepts
  `cheque` and `bank_transfer`.
* `accounting.cash_handover_review` (new, append-only, one per handover):
  the accountant's accept/dispute decision on a driver's cash handover.
* Permissions `invoices:issue` (issue an invoice held for missing GST
  configuration) and `cash_handovers:review` for super_admin, agency_admin,
  manager and accountant.
* DA-31: invoices created without a number (seeded data) are numbered from
  the tenant's `invoice` reference sequence, oldest first.

Revision ID: e7b3c9d1f4a6
Revises: c8d4e2f6a1b3
Create Date: 2026-10-20
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "e7b3c9d1f4a6"
down_revision: str | None = "c8d4e2f6a1b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_LPG_HSN = "27111900"
_REVIEW_TABLE = "accounting.cash_handover_review"
_ROLES_SQL = "('super_admin', 'agency_admin', 'manager', 'accountant')"
_PERMISSIONS = (
    ("invoices:issue", "invoices", "issue"),
    ("cash_handovers:review", "cash_handovers", "review"),
)
_PAYMENT_METHODS_OLD = "('cash', 'upi', 'card', 'online_gateway', 'credit')"
_PAYMENT_METHODS_NEW = (
    "('cash', 'upi', 'card', 'online_gateway', 'credit', 'cheque', 'bank_transfer')"
)


def _app_role_sql(statement: str) -> str:
    return f"""
        DO $$
        DECLARE
            app_role text := CASE current_database()
                WHEN 'lpg_uat' THEN 'lpg_app_uat'
                ELSE 'lpg_app'
            END;
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = app_role) THEN
                EXECUTE format('{statement}', app_role);
            END IF;
        END
        $$;
    """


def _upgrade_tenant() -> None:
    op.execute("""
        ALTER TABLE tenant.cylinder_type
            ADD COLUMN hsn_code varchar(8)
                CHECK (hsn_code ~ '^([0-9]{4}|[0-9]{6}|[0-9]{8})$'),
            ADD COLUMN gst_rate_percent numeric(5, 2)
                CHECK (gst_rate_percent >= 0 AND gst_rate_percent <= 28)
    """)
    op.execute(f"UPDATE tenant.cylinder_type SET hsn_code = '{_LPG_HSN}'")
    op.execute("""
        ALTER TABLE tenant.tenant
            ADD COLUMN legal_name varchar(200),
            ADD COLUMN gstin varchar(15),
            ADD COLUMN address_line_1 varchar(200),
            ADD COLUMN address_line_2 varchar(200),
            ADD COLUMN city varchar(100),
            ADD COLUMN state_code varchar(2),
            ADD COLUMN pincode varchar(6),
            ADD COLUMN phone varchar(20)
    """)


def _upgrade_invoice() -> None:
    op.execute("""
        ALTER TABLE accounting.invoice
            ADD COLUMN supplier_state_code varchar(2),
            ADD COLUMN place_of_supply_state_code varchar(2),
            ADD COLUMN customer_gstin varchar(15)
    """)
    op.execute("""
        ALTER TABLE accounting.invoice_line
            ADD COLUMN hsn_code varchar(8),
            ADD COLUMN gst_rate_percent numeric(5, 2),
            ADD COLUMN line_kind varchar(30) NOT NULL DEFAULT 'supply'
                CONSTRAINT ck_invoice_line_kind
                CHECK (line_kind IN ('supply', 'cancellation_charge')),
            ADD COLUMN description varchar(200)
    """)
    op.execute("ALTER TABLE accounting.payment ADD COLUMN reference varchar(100)")
    op.execute("ALTER TABLE accounting.payment DROP CONSTRAINT payment_method_check")
    op.execute(
        "ALTER TABLE accounting.payment ADD CONSTRAINT payment_method_check "
        f"CHECK (method IN {_PAYMENT_METHODS_NEW})"
    )


def _backfill_per_tenant() -> None:
    """Every accounting table is under FORCE ROW LEVEL SECURITY, so the
    backfill runs once per tenant with `app.current_tenant_id` set.
    """
    op.execute(f"""
        DO $$
        DECLARE
            t uuid;
            numbered integer;
        BEGIN
            FOR t IN SELECT id FROM tenant.tenant LOOP
                PERFORM set_config('app.current_tenant_id', t::text, true);

                UPDATE accounting.invoice_line
                SET gst_rate_percent = CASE
                        WHEN subtotal > 0 THEN ROUND(tax_amount / subtotal * 100, 2)
                        ELSE 0
                    END,
                    hsn_code = '{_LPG_HSN}'
                WHERE gst_rate_percent IS NULL;

                INSERT INTO platform.reference_number_sequence (tenant_id, entity_type, next_value)
                VALUES (t, 'invoice', 1)
                ON CONFLICT (tenant_id, entity_type) DO NOTHING;

                WITH unnumbered AS (
                    SELECT i.id, i.issued_at,
                           ROW_NUMBER() OVER (ORDER BY i.issued_at, i.id) AS n
                    FROM accounting.invoice i
                    WHERE i.invoice_number IS NULL
                ),
                seq AS (
                    SELECT next_value FROM platform.reference_number_sequence
                    WHERE tenant_id = t AND entity_type = 'invoice'
                )
                UPDATE accounting.invoice i
                SET invoice_number = 'INV-'
                        || EXTRACT(YEAR FROM u.issued_at AT TIME ZONE 'UTC')::int
                        || '-' || LPAD((seq.next_value + u.n - 1)::text, 6, '0')
                FROM unnumbered u, seq
                WHERE i.id = u.id;
                GET DIAGNOSTICS numbered = ROW_COUNT;

                UPDATE platform.reference_number_sequence
                SET next_value = next_value + numbered
                WHERE tenant_id = t AND entity_type = 'invoice';
            END LOOP;
        END
        $$;
    """)


def _upgrade_cash_handover_review() -> None:
    op.execute(f"""
        CREATE TABLE {_REVIEW_TABLE} (
            id uuid PRIMARY KEY,
            tenant_id uuid NOT NULL REFERENCES tenant.tenant(id) ON DELETE CASCADE,
            cash_handover_id uuid NOT NULL UNIQUE
                REFERENCES accounting.cash_handover(id) ON DELETE CASCADE,
            outcome varchar(20) NOT NULL CHECK (outcome IN ('accepted', 'disputed')),
            note text,
            reviewed_by uuid NOT NULL,
            reviewed_at timestamptz NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute(
        f"CREATE INDEX idx_accounting_cash_handover_review_tenant ON {_REVIEW_TABLE} (tenant_id)"
    )
    op.execute(_app_role_sql("GRANT USAGE ON SCHEMA accounting TO %I"))
    op.execute(_app_role_sql(f"GRANT SELECT, INSERT ON {_REVIEW_TABLE} TO %I"))
    op.execute(_app_role_sql(f"REVOKE UPDATE, DELETE ON {_REVIEW_TABLE} FROM %I"))
    op.execute(f"ALTER TABLE {_REVIEW_TABLE} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {_REVIEW_TABLE} FORCE ROW LEVEL SECURITY")
    op.execute(f"""
        CREATE POLICY rls_accounting_cash_handover_review_isolation ON {_REVIEW_TABLE}
        USING (
            tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
        )
    """)


def _upgrade_permissions() -> None:
    for code, resource, action in _PERMISSIONS:
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
            WHERE r.code IN {_ROLES_SQL} AND p.code = '{code}'
            ON CONFLICT (role_id, permission_id) DO NOTHING
        """)
        # Permission resolution is per user (see c039189dfbdc), so existing
        # users of those roles are backfilled too.
        op.execute(f"""
            INSERT INTO identity.identity_user_permission (id, user_id, permission_id, created_at)
            SELECT gen_random_uuid(), u.id, p.id, now()
            FROM identity.identity_user u
            JOIN identity.permission p ON p.code = '{code}'
            WHERE u.role IN {_ROLES_SQL}
              AND NOT EXISTS (
                  SELECT 1 FROM identity.identity_user_permission existing
                  WHERE existing.user_id = u.id AND existing.permission_id = p.id
              )
        """)


def upgrade() -> None:
    _upgrade_tenant()
    _upgrade_invoice()
    _backfill_per_tenant()
    _upgrade_cash_handover_review()
    _upgrade_permissions()


def downgrade() -> None:
    codes = ", ".join(f"'{code}'" for code, _, _ in _PERMISSIONS)
    permission_ids = f"SELECT id FROM identity.permission WHERE code IN ({codes})"
    op.execute(
        f"DELETE FROM identity.identity_user_permission WHERE permission_id IN ({permission_ids})"
    )
    op.execute(f"DELETE FROM identity.role_permission WHERE permission_id IN ({permission_ids})")
    op.execute(f"DELETE FROM identity.permission WHERE code IN ({codes})")

    op.execute(f"DROP TABLE IF EXISTS {_REVIEW_TABLE}")

    # Invoice numbers assigned by the backfill are kept: they may already
    # have been printed or shared.
    op.execute("ALTER TABLE accounting.payment DROP CONSTRAINT payment_method_check")
    op.execute(
        "ALTER TABLE accounting.payment ADD CONSTRAINT payment_method_check "
        f"CHECK (method IN {_PAYMENT_METHODS_OLD}) NOT VALID"
    )
    op.execute("ALTER TABLE accounting.payment DROP COLUMN reference")
    op.execute("""
        ALTER TABLE accounting.invoice_line
            DROP COLUMN description,
            DROP COLUMN line_kind,
            DROP COLUMN gst_rate_percent,
            DROP COLUMN hsn_code
    """)
    op.execute("""
        ALTER TABLE accounting.invoice
            DROP COLUMN customer_gstin,
            DROP COLUMN place_of_supply_state_code,
            DROP COLUMN supplier_state_code
    """)
    op.execute("""
        ALTER TABLE tenant.tenant
            DROP COLUMN phone,
            DROP COLUMN pincode,
            DROP COLUMN state_code,
            DROP COLUMN city,
            DROP COLUMN address_line_2,
            DROP COLUMN address_line_1,
            DROP COLUMN gstin,
            DROP COLUMN legal_name
    """)
    op.execute("""
        ALTER TABLE tenant.cylinder_type
            DROP COLUMN gst_rate_percent,
            DROP COLUMN hsn_code
    """)
