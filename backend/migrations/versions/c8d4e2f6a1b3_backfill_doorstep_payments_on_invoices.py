"""backfill doorstep payments onto invoices

Until now the payment a driver recorded at delivery (cash, UPI, card or
online, stored on `orders.proof_of_delivery`) never reached the order's
invoice, so a delivery paid at the door left an `issued` invoice and the
Customer App kept offering "Pay Online" for money already collected.
Invoice generation now records that collection as an invoice payment
(`payment-flow.md` Path B step 4); this migration does the same for
invoices generated before the fix.

Same rule as `apply_doorstep_collection_to_invoice`: only invoices still
`issued`/`partially_paid`, only the outstanding balance, never `credit`.
Every accounting/orders table is under FORCE ROW LEVEL SECURITY, so the
backfill runs once per tenant with `app.current_tenant_id` set.
`accounting.payment` is append-only, so there is no data downgrade.

Revision ID: c8d4e2f6a1b3
Revises: b7e1d3f5a2c9
Create Date: 2026-10-19
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "c8d4e2f6a1b3"
down_revision: str | None = "b7e1d3f5a2c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        DECLARE
            t uuid;
        BEGIN
            FOR t IN SELECT id FROM tenant.tenant LOOP
                PERFORM set_config('app.current_tenant_id', t::text, true);

                INSERT INTO accounting.payment (
                    id, tenant_id, invoice_id, method, amount, collected_by, collected_at
                )
                SELECT gen_random_uuid(), i.tenant_id, i.id, pod.payment_method,
                       LEAST(pod.amount_collected, i.total_amount - COALESCE(paid.amount, 0)),
                       pod.recorded_by, pod.recorded_at
                FROM accounting.invoice i
                JOIN LATERAL (
                    SELECT p.payment_method, p.amount_collected, p.recorded_by, p.recorded_at
                    FROM orders.proof_of_delivery p
                    WHERE p.order_id = i.order_id
                    ORDER BY p.recorded_at DESC
                    LIMIT 1
                ) pod ON true
                LEFT JOIN LATERAL (
                    SELECT SUM(ap.amount) AS amount
                    FROM accounting.payment ap
                    WHERE ap.invoice_id = i.id
                ) paid ON true
                WHERE i.status IN ('issued', 'partially_paid')
                  AND pod.payment_method IN ('cash', 'upi', 'card', 'online_gateway')
                  AND pod.amount_collected > 0
                  AND i.total_amount - COALESCE(paid.amount, 0) > 0;

                UPDATE accounting.invoice i
                SET status = CASE
                        WHEN paid.amount >= i.total_amount THEN 'paid'
                        ELSE 'partially_paid'
                    END,
                    version = i.version + 1
                FROM (
                    SELECT invoice_id, SUM(amount) AS amount
                    FROM accounting.payment
                    GROUP BY invoice_id
                ) paid
                WHERE paid.invoice_id = i.id
                  AND i.status IN ('issued', 'partially_paid')
                  AND paid.amount > 0
                  AND i.status IS DISTINCT FROM CASE
                        WHEN paid.amount >= i.total_amount THEN 'paid'
                        ELSE 'partially_paid'
                    END;
            END LOOP;
            PERFORM set_config('app.current_tenant_id', '', true);
        END
        $$;
        """
    )


def downgrade() -> None:
    # Payments are append-only records of money actually collected; there
    # is nothing to undo.
    pass
