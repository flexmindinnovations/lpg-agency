# 44 — Book only orderable cylinders — Status

**2026-10-19 — Implemented.** Backend ruff, ruff format, mypy --strict,
import-linter and the unit suite pass; order, route, WhatsApp and job
integration tests pass against a local PostgreSQL 16. Dashboard lint, tests
and build pass for the affected projects. Flutter is not installed in the cloud
session, so the Customer App change is verified by Mobile CI only and needs a
new APK. The backend and dashboard deploy on merge.

**2026-11-26 — Staff see why a type is missing.** New staff-only endpoint
`GET /orders/unorderable-cylinder-types` (`orders:create`; customer logins get
403) lists each active type the customer cannot book, with the reason: no price
for their customer type at the branch, no free filled stock, or both. The
dashboard booking form shows it. If that request fails, the form shows the
general message and booking is unaffected. The Customer App is unchanged.
Verified: backend ruff, format, mypy, import-linter, OpenAPI check and 1822
unit tests; the orderable-type database tests on a temporary local database;
frontend tests, lint and build; the form in a headless browser with a faked API.
