"""One-time backfill of human-readable reference numbers for rows that
predate the reference-number migration series
(`f3a7c2e8d4b1`/`b8d4f1a9c6e3`).

Run once per environment, AFTER those two migrations are applied and
BEFORE the corresponding application code deploys (so freshly-generated
numbers never collide with numbers this script is about to assign) —
see the plan's "Backfill strategy" section for why this ordering matters.

Idempotent: every UPDATE is scoped to `WHERE <number_col> IS NULL`, so a
partial or repeated run only touches rows that still need a number.

Usage:
    python -m scripts.backfill_reference_numbers
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from lpg.config.settings import get_settings


@dataclass(frozen=True)
class SimpleBackfillTarget:
    """A table whose reference number is a plain `PREFIX{seq:0Nd}` — no
    year segment, no denormalized foreign fields. Order/Complaint/
    CreditNote/CashHandover/GRN all fit this shape.
    """

    schema: str
    table: str
    number_col: str
    order_by_col: str
    entity_type: str
    prefix: str
    pad_width: int


_SIMPLE_TARGETS = [
    SimpleBackfillTarget("orders", "order", "order_number", "requested_date", "order", "ORD", 6),
    SimpleBackfillTarget(
        "complaint", "complaint", "complaint_number", "created_at", "complaint", "CMP", 6
    ),
    SimpleBackfillTarget(
        "accounting", "credit_note", "credit_note_number", "requested_at", "credit_note", "CRN", 6
    ),
    SimpleBackfillTarget(
        "accounting", "cash_handover", "handover_number", "declared_at", "cash_handover", "CSH", 6
    ),
    SimpleBackfillTarget(
        "inventory", "goods_receipt_note", "grn_number", "received_at", "grn", "GRN", 6
    ),
]


async def _backfill_simple_target(conn, target: SimpleBackfillTarget) -> None:
    # S608: the interpolated parts (schema/table/column names) all come from
    # the hardcoded `_SIMPLE_TARGETS` list above, never from user input —
    # only the actual values (tenant_id, row_id, number) are real
    # parameters, bound via SQLAlchemy's `:name` placeholders below.
    tenant_rows = await conn.execute(
        text(
            f"SELECT DISTINCT tenant_id FROM {target.schema}.{target.table} "  # noqa: S608
            f"WHERE {target.number_col} IS NULL"
        )
    )
    tenant_ids = [row[0] for row in tenant_rows]

    for tenant_id in tenant_ids:
        rows = await conn.execute(
            text(
                f"SELECT id FROM {target.schema}.{target.table} "  # noqa: S608
                f"WHERE tenant_id = :tenant_id AND {target.number_col} IS NULL "
                f"ORDER BY {target.order_by_col} ASC"
            ),
            {"tenant_id": tenant_id},
        )
        row_ids = [row[0] for row in rows]
        if not row_ids:
            continue

        for index, row_id in enumerate(row_ids, start=1):
            number = f"{target.prefix}{index:0{target.pad_width}d}"
            await conn.execute(
                text(
                    f"UPDATE {target.schema}.{target.table} "  # noqa: S608
                    f"SET {target.number_col} = :number WHERE id = :row_id"
                ),
                {"number": number, "row_id": row_id},
            )

        await _prime_counter(conn, tenant_id, target.entity_type, len(row_ids) + 1)
        print(
            f"  {target.schema}.{target.table}: backfilled {len(row_ids)} row(s) "
            f"for tenant {tenant_id}"
        )


async def _prime_counter(conn, tenant_id, entity_type: str, next_value: int) -> None:
    """Advance `platform.reference_number_sequence.next_value` to at least
    `next_value`, so the first `.next()` call after this script runs
    continues cleanly from the backfilled numbers instead of colliding
    with them. Never moves the counter backwards — a tenant that already
    had live traffic issuing real numbers before this script ran (e.g. a
    re-run after some new rows were created) must not have its counter
    regress.
    """
    await conn.execute(
        text("""
            INSERT INTO platform.reference_number_sequence (tenant_id, entity_type, next_value)
            VALUES (:tenant_id, :entity_type, :next_value)
            ON CONFLICT (tenant_id, entity_type) DO UPDATE
            SET next_value = GREATEST(
                platform.reference_number_sequence.next_value, EXCLUDED.next_value
            )
        """),
        {"tenant_id": tenant_id, "entity_type": entity_type, "next_value": next_value},
    )


async def _backfill_invoices(conn) -> None:
    """Invoice is a bespoke case: the number includes the issuance year
    (read from each row's own `issued_at`, not "now"), and two other
    columns (`order_number`, `customer_consumer_number`) are denormalized
    joins rather than a sequence — run after Order's own backfill so
    `orders.order.order_number` is already populated to join from.
    """
    tenant_rows = await conn.execute(
        text("SELECT DISTINCT tenant_id FROM accounting.invoice WHERE invoice_number IS NULL")
    )
    tenant_ids = [row[0] for row in tenant_rows]

    for tenant_id in tenant_ids:
        rows = await conn.execute(
            text(
                "SELECT id, EXTRACT(YEAR FROM issued_at)::int AS year "
                "FROM accounting.invoice "
                "WHERE tenant_id = :tenant_id AND invoice_number IS NULL "
                "ORDER BY issued_at ASC"
            ),
            {"tenant_id": tenant_id},
        )
        invoice_rows = [(row[0], row[1]) for row in rows]
        if not invoice_rows:
            continue

        for index, (invoice_id, year) in enumerate(invoice_rows, start=1):
            number = f"INV-{year}-{index:06d}"
            await conn.execute(
                text(
                    "UPDATE accounting.invoice SET invoice_number = :number WHERE id = :invoice_id"
                ),
                {"number": number, "invoice_id": invoice_id},
            )

        await _prime_counter(conn, tenant_id, "invoice", len(invoice_rows) + 1)
        print(f"  accounting.invoice: backfilled {len(invoice_rows)} row(s) for tenant {tenant_id}")

    # Denormalized joins — independent of the numbering above, safe to
    # run every time (idempotent via the IS NULL guard).
    result = await conn.execute(
        text("""
            UPDATE accounting.invoice i
            SET order_number = o.order_number
            FROM orders.order o
            WHERE o.id = i.order_id AND i.order_number IS NULL AND o.order_number IS NOT NULL
        """)
    )
    print(f"  accounting.invoice.order_number: denormalized {result.rowcount} row(s)")

    result = await conn.execute(
        text("""
            UPDATE accounting.invoice i
            SET customer_consumer_number = c.consumer_number
            FROM customer.customer c
            WHERE c.id = i.customer_id
              AND i.customer_consumer_number IS NULL
              AND c.consumer_number IS NOT NULL
        """)
    )
    print(f"  accounting.invoice.customer_consumer_number: denormalized {result.rowcount} row(s)")


async def _reseed_employee_counters(conn) -> None:
    """`employee_code` is never NULL — every employee already has one,
    issued off the old global `tenant.employee_code_seq`. This isn't a row
    backfill; it primes each tenant's new counter above the highest
    numeric suffix that tenant has ever been issued, so newly-issued
    codes (now generated per-tenant) never collide with old ones — then
    drops the old, non-tenant-scoped sequence.
    """
    rows = await conn.execute(
        text("""
            SELECT tenant_id, MAX(SUBSTRING(employee_code FROM 4)::int) AS max_seq
            FROM tenant.employee
            WHERE employee_code ~ '^EMP[0-9]+$'
            GROUP BY tenant_id
        """)
    )
    for tenant_id, max_seq in rows:
        await _prime_counter(conn, tenant_id, "employee", (max_seq or 0) + 1)
    print(f"  tenant.employee: primed per-tenant counters for {rows.rowcount} tenant(s)")

    await conn.execute(text("DROP SEQUENCE IF EXISTS tenant.employee_code_seq"))
    print("  dropped tenant.employee_code_seq")


async def main() -> None:
    settings = get_settings()
    dsn = settings.migration_database_url or (
        "postgresql+asyncpg://lpg_admin:dev_only_not_a_real_secret@localhost:55432/lpg_dev"
    )
    print(f"Connecting to database using DSN: {dsn}")
    engine = create_async_engine(str(dsn))

    async with engine.begin() as conn:
        for target in _SIMPLE_TARGETS:
            print(f"Backfilling {target.schema}.{target.table}...")
            await _backfill_simple_target(conn, target)

        print("Backfilling accounting.invoice...")
        await _backfill_invoices(conn)

        print("Re-seeding employee_code counters...")
        await _reseed_employee_counters(conn)

    await engine.dispose()
    print("\nBackfill complete.")


if __name__ == "__main__":
    asyncio.run(main())
