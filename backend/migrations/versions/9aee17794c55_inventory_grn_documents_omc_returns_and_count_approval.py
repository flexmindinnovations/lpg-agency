"""inventory: GRN documents, empties return to OMC, maker-checker stock counts

Revision ID: 9aee17794c55
Revises: c8d4e2f6a1b3
Create Date: 2026-10-20 14:00:00.000000

QA fixes DA-02/DA-04/DA-34/DO-32:

- `inventory.goods_receipt_note` gains the OMC challan number, tax-invoice
  number and truck number the agency checks a receipt against.
- New `inventory.omc_return_note` — empties (or segregated defective
  cylinders) dispatched back to the bottling plant, numbered ERN000001.
  `inventory_transaction.transaction_type` gains `omc_return`.
- `inventory.reconciliation_record` gains a reject path (`rejected_by`,
  `rejected_at`, `rejection_reason`). Counts no longer change stock until
  approved, so any count still pending from before this release — whose
  stock was already corrected when it was recorded — is closed here, so it
  can never be approved and booked a second time.
- `compliance.cylinder_unit`: a unit never tested gets its first statutory
  test due date from its manufacture date (Gas Cylinders Rules 2016: first
  periodic test of an LPG cylinder 10 years after manufacture).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "9aee17794c55"
down_revision: str | None = "c8d4e2f6a1b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "inventory"
_TENANT_SCHEMA = "tenant"
# See `95eff999e568` for why the constraint name is doubled on disk.
_TYPE_CONSTRAINT = "ck_inventory_transaction_ck_inventory_transaction_type"
_PREVIOUS_TYPES = (
    "grn_receipt",
    "load",
    "unload",
    "delivery",
    "collection",
    "status_change",
    "adjustment",
    "reconciliation",
    "reservation",
    "reservation_release",
)
_TYPES = (*_PREVIOUS_TYPES, "omc_return")
_OMCS = ("iocl", "bpcl", "hpcl", "other")
_RETURNABLE_STATUSES = ("empty", "damaged", "leakage", "quarantine")
_FIRST_TEST_YEARS = 10


def _app_role_grant(table: str) -> str:
    return f"""
        DO $$
        DECLARE
            app_role text := CASE current_database()
                WHEN 'lpg_uat' THEN 'lpg_app_uat'
                ELSE 'lpg_app'
            END;
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = app_role) THEN
                EXECUTE format('GRANT SELECT, INSERT, UPDATE ON {_SCHEMA}.{table} TO %I', app_role);
            END IF;
        END
        $$;
    """


def upgrade() -> None:
    # 1. GRN document references.
    for column, length in (("challan_number", 50), ("invoice_number", 50), ("truck_number", 20)):
        op.add_column(
            "goods_receipt_note",
            sa.Column(column, sa.String(length=length), nullable=True),
            schema=_SCHEMA,
        )

    # 2. omc_return transaction type.
    op.execute(f"ALTER TABLE {_SCHEMA}.inventory_transaction DROP CONSTRAINT {_TYPE_CONSTRAINT}")
    op.execute(
        f"ALTER TABLE {_SCHEMA}.inventory_transaction "
        f"ADD CONSTRAINT {_TYPE_CONSTRAINT} CHECK (transaction_type IN {_TYPES})"
    )

    # 3. Empties return note.
    op.create_table(
        "omc_return_note",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "tenant_id",
            sa.Uuid(),
            sa.ForeignKey(f"{_TENANT_SCHEMA}.tenant.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("return_number", sa.String(length=20), nullable=False),
        sa.Column(
            "warehouse_id",
            sa.Uuid(),
            sa.ForeignKey(f"{_TENANT_SCHEMA}.warehouse.id"),
            nullable=False,
        ),
        sa.Column(
            "cylinder_type_id",
            sa.Uuid(),
            sa.ForeignKey(f"{_TENANT_SCHEMA}.cylinder_type.id"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("destination_omc", sa.String(length=20), nullable=False),
        sa.Column("challan_number", sa.String(length=50), nullable=True),
        sa.Column("truck_number", sa.String(length=20), nullable=True),
        sa.Column("dispatched_by", sa.Uuid(), nullable=False),
        sa.Column(
            "dispatched_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
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
        sa.CheckConstraint("quantity > 0", name="quantity_positive"),
        sa.CheckConstraint(f"destination_omc IN {_OMCS}", name="destination_omc"),
        sa.CheckConstraint(f"status IN {_RETURNABLE_STATUSES}", name="status"),
        sa.UniqueConstraint("tenant_id", "return_number", name="uq_omc_return_note_number"),
        schema=_SCHEMA,
    )
    op.create_index(
        "idx_omc_return_note_warehouse_dispatched_at",
        "omc_return_note",
        ["warehouse_id", "dispatched_at"],
        schema=_SCHEMA,
    )
    op.execute(f"ALTER TABLE {_SCHEMA}.omc_return_note ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {_SCHEMA}.omc_return_note FORCE ROW LEVEL SECURITY")
    op.execute(f"""
        CREATE POLICY rls_{_SCHEMA}_omc_return_note_isolation ON {_SCHEMA}.omc_return_note
        USING (
            tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
        )
    """)
    op.execute(_app_role_grant("omc_return_note"))

    # 4. Reconciliation reject path, and close counts already booked.
    op.add_column(
        "reconciliation_record", sa.Column("rejected_by", sa.Uuid(), nullable=True), schema=_SCHEMA
    )
    op.add_column(
        "reconciliation_record",
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        schema=_SCHEMA,
    )
    op.add_column(
        "reconciliation_record",
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        schema=_SCHEMA,
    )
    op.create_check_constraint(
        "single_decision",
        "reconciliation_record",
        "approved_at IS NULL OR rejected_at IS NULL",
        schema=_SCHEMA,
    )
    op.execute(f"""
        UPDATE {_SCHEMA}.reconciliation_record
        SET rejected_at = now(),
            rejection_reason = 'Closed on upgrade: this count already corrected stock '
                               'when it was recorded, so it cannot be approved again.'
        WHERE approved_at IS NULL AND rejected_at IS NULL
    """)

    # 5. First statutory test due date for never-tested cylinder units.
    op.execute(f"""
        UPDATE compliance.cylinder_unit
        SET test_due_date = (manufacture_date + interval '{_FIRST_TEST_YEARS} years')::date
        WHERE test_due_date IS NULL
          AND last_tested_at IS NULL
          AND manufacture_date IS NOT NULL
    """)


def downgrade() -> None:
    # The cylinder due dates and closed counts are data corrections and stay.
    op.drop_constraint(
        "ck_reconciliation_record_single_decision", "reconciliation_record", schema=_SCHEMA
    )
    for column in ("rejection_reason", "rejected_at", "rejected_by"):
        op.drop_column("reconciliation_record", column, schema=_SCHEMA)

    op.drop_index(
        "idx_omc_return_note_warehouse_dispatched_at", table_name="omc_return_note", schema=_SCHEMA
    )
    op.drop_table("omc_return_note", schema=_SCHEMA)

    op.execute(f"ALTER TABLE {_SCHEMA}.inventory_transaction DROP CONSTRAINT {_TYPE_CONSTRAINT}")
    op.execute(
        f"ALTER TABLE {_SCHEMA}.inventory_transaction "
        f"ADD CONSTRAINT {_TYPE_CONSTRAINT} CHECK (transaction_type IN {_PREVIOUS_TYPES}) NOT VALID"
    )

    for column in ("truck_number", "invoice_number", "challan_number"):
        op.drop_column("goods_receipt_note", column, schema=_SCHEMA)
