# Status: Agency User Management

**Phase:** 31
**Status:** Built and verified locally 2026-09-26; **not yet deployed**.

## Verified (gates re-run, output seen)

| Gate | Result |
|---|---|
| `ruff check` / `ruff format --check` (backend) | clean |
| `mypy` strict (516 files) | clean |
| `lint-imports` | 6 contracts kept, 0 broken |
| OpenAPI drift check | matches |
| Backend unit tests (whole suite) | 1,039 pass |
| New integration tests, real PostgreSQL | 7 pass |
| Related integration + tenant-isolation tests | 182 pass |
| Live HTTP walkthrough (local stack) | 15 checks as expected (see below) |
| Frontend `nx test` + `nx lint`: `platform-feature-agencies`, `shared-data-access` | 23 + 53 pass, lint 0 errors |
| `nx build dashboard` (AOT, production) | passes (pre-existing bundle-size warning only) |
| UI in a real browser (local dev servers) | users list, add admin, validation, duplicate-email error toast, new setup link, Create agency via the shared drawer |

HTTP walkthrough: add admin 201, same email 409, re-issue 201, old link 410, new link 204, reused link 410, stranger's user 404, unknown agency 404, malformed id 422, no token 401, 24 h expiry, both audit rows attributed to the agency.

## Not verified

- Production deployment of this change.
- Light theme and narrow/mobile widths for the new Users block.
- An agency-admin token against the new routes over HTTP (the new admin was blocked by the license gate first); the platform-principal boundary is covered by the existing `test_platform_rbac.py`, which passes.

Design: [PLAN.md](./PLAN.md). Tasks: [TASKS.md](./TASKS.md). Decision: ADR-049.
