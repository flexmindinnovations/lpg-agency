# 47 — QA fixes — Status

**2026-10-21 — Implemented.** All seven areas merged on one branch. Backend
ruff, ruff format, mypy --strict and import-linter pass, and the full pytest
suite passes against a local PostgreSQL 16 apart from the tests already
failing on main (`test_database.py`, `test_employee_endpoints_smoke.py`).
Dashboard lint, unit tests and production build pass. Flutter analyze and
tests pass for both apps.

Before production use:
- Set `LPG_DASHBOARD_URL` (account setup and reset e-mails link to it).
- Set the HSN code and GST rate on every cylinder type; until then invoices
  are held with `GST_NOT_CONFIGURED`.
- The deploy now fails the dashboard build if the PrimeNG licence secret is
  empty.
- E-mail, SMS and push still need the arq worker; in-app notifications no
  longer do.
- Rebuild both APKs.

Migrations: `9aee17794c55`, `c48cbf996d8c`, `21a625272f0b`, `a9d2197ebb9b`,
`e7b3c9d1f4a6`, `7bc2ddcd8ed9`.
