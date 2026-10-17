# Status: Online Payments (Razorpay)

**Status:** Built and tested 2026-10-17 against a stubbed gateway. **Not yet run against real Razorpay test keys.**

## Verified (gates re-run, output seen)

| Gate | Result |
|---|---|
| `ruff check`, `ruff format --check` | clean |
| `mypy --strict` | clean (537 files) |
| `lint-imports` | 6 contracts kept |
| `export_openapi.py` | regenerated, committed |
| Migration `a9e4c7b2d1f6` upgrade, downgrade, upgrade | clean |
| `tests/unit/test_online_payments.py` (29) | pass |
| `tests/integration/test_online_payment_endpoints_smoke.py` (7) | pass, real PostgreSQL + Redis |
| Full backend suite (local PostgreSQL 16 + Redis + moto S3) | 1582 passed, 4 failed |
| `flutter analyze` (api_client, customer_app) | no issues |
| `flutter test` (customer_app 48, api_client payment tests 3) | pass |

The 4 backend failures fail identically on `main` in this environment (checked on a clean worktree: 1546 passed, same 4 failed): the PostgreSQL 17 version check (16 was used) and three employee-registration tests hitting an existing foreign-key error.

## Not verified

- Real Razorpay test-mode calls and webhook delivery (needs keys and a public URL).
- The Pay Online flow on a phone.

Design: [PLAN.md](./PLAN.md). Tasks: [TASKS.md](./TASKS.md). Decision: ADR-052.
