"""grant update on accounting.invoice

R10 (`PaymentCollected`): `Invoice.record_payment()` transitions `status`
(`issued` -> `partially_paid` -> `paid`), and `SqlAlchemyInvoiceRepository.
save()` persists that with `UPDATE accounting.invoice SET status = ...`.

`e60b8b86b965` (2026-08-13) revoked `UPDATE, DELETE` on `accounting.invoice`
when the schema was first created — a reasonable choice at the time, since
nothing mutated an existing invoice row; `add()` was, and until this
migration remained, the only write path. Found the hard way: every real
payment attempt failed with `InsufficientPrivilegeError` in integration
testing (`test_record_partial_then_full_payment_moves_status_to_paid`)
before this migration existed.

`DELETE` stays revoked — invoices are still never deleted, only
transitioned. `invoice_line` and `payment` both stay `SELECT, INSERT` only,
unchanged — no code path updates either.

Revision ID: 6ae4682bd49d
Revises: 11ddf55a78ed
Create Date: 2026-08-19
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "6ae4682bd49d"
down_revision: str | None = "11ddf55a78ed"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        DO $$
        DECLARE
            app_role text := CASE current_database()
                WHEN 'lpg_uat' THEN 'lpg_app_uat'
                ELSE 'lpg_app'
            END;
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = app_role) THEN
                EXECUTE format('GRANT UPDATE ON accounting.invoice TO %I', app_role);
            END IF;
        END
        $$;
    """)


def downgrade() -> None:
    op.execute("""
        DO $$
        DECLARE
            app_role text := CASE current_database()
                WHEN 'lpg_uat' THEN 'lpg_app_uat'
                ELSE 'lpg_app'
            END;
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = app_role) THEN
                EXECUTE format('REVOKE UPDATE ON accounting.invoice FROM %I', app_role);
            END IF;
        END
        $$;
    """)
