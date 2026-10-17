# Status: WhatsApp AI Customer Assistant

**Status:** Built and tested 2026-10-17. **Not yet tried against a real Meta number.**

## Verified (gates re-run, output seen)

| Gate | Result |
|---|---|
| `ruff check`, `ruff format --check` | clean |
| `mypy --strict` | clean (545 files) |
| `lint-imports` | 7 contracts kept (one new) |
| `export_openapi.py --check` | no drift (webhook is excluded from the schema) |
| Alembic upgrade / downgrade / re-upgrade of `a9c2e4f6b8d1` | clean |
| New unit tests (adapter, webhook, assistant) | pass |
| New integration tests `test_whatsapp_assistant_smoke.py` (7) | pass, against real PostgreSQL + Redis |
| Full backend suite (local PostgreSQL 16 + Redis, fake S3) | 1583 passed, 11 failed |

The 11 failures are outside this feature and environmental or pre-existing:
one PostgreSQL 17 version check (16 was used), six file-storage tests and
one KYC-recognition test that need a real MinIO, and three
employee-registration tests that fail identically on the base branch (the
existing `EmployeeRegistered` handler's foreign-key error).

## Not verified

- A real WhatsApp conversation through Meta's Cloud API and a real Claude call.
- Dashboard settings page lint/tests (frontend `node_modules` not installed here).

Design: [PLAN.md](./PLAN.md). Tasks: [TASKS.md](./TASKS.md). Decision: ADR-052.
