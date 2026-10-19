# 43 — Post-delivery customer actions — Status

**2026-10-19 — Done.** Backend ruff, ruff format, mypy --strict, import-linter,
OpenAPI drift check and the unit suite pass. Migration `c8d4e2f6a1b3` was run
against a local PostgreSQL 16 with seeded invoices (cash in full, UPI part
payment, credit, already-paid, over-collection) and gave the expected
statuses; re-running it adds nothing. `get_by_order_id` checked as `lpg_app`
under RLS, including another tenant seeing nothing. Customer App:
`flutter analyze` and `flutter test` pass. The Customer App needs a new APK.
