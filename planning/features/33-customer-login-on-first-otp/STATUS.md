# Status: Customer App Login on First OTP Sign-in

**Status:** Built and tested 2026-10-15. **Not yet tried on a phone against UAT.**

## Verified (gates re-run, output seen)

| Gate | Result |
|---|---|
| `ruff check`, `ruff format --check` | clean |
| `mypy --strict` | clean (519 files) |
| `lint-imports` | 6 contracts kept |
| `export_openapi.py --check` | no drift (no API change) |
| New tests: `test_domain_customer.py` (7), `test_auth_flows.py::TestCustomerLoginOnFirstOtp` (6) | pass, against real PostgreSQL + Redis |
| Full backend suite (local PostgreSQL 16 + Redis, no MinIO) | 1488 passed, 8 skipped, 7 failed |

The 7 failures fail the same way on `main` in this environment: one PostgreSQL 17 version check (16 was used), two KYC-upload tests that need MinIO, one order-lifecycle test, and three employee-registration tests that hit a foreign-key error in the existing `EmployeeRegistered` handler.

## Not verified

- Signing in on a phone against UAT after deploy.

Design: [PLAN.md](./PLAN.md). Tasks: [TASKS.md](./TASKS.md). Decision: ADR-051.
