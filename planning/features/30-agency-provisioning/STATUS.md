# Status: Agency Provisioning

**Phase:** 30
**Status:** Backend done and verified 2026-09-25; the Create-agency UI is tested
by component tests only and has **not been exercised in a browser**.

## Verified (gates re-run, output seen)

| Gate | Result |
|---|---|
| `ruff check` (backend `src` + `tests`) | clean |
| `mypy` (strict, 512 files) | clean |
| `lint-imports` | 6 contracts kept, 0 broken |
| Backend unit tests (whole suite) | 1,025 pass |
| New integration tests, real PostgreSQL | 6 pass |
| Related integration + tenant-isolation tests | 175 pass |
| Frontend `nx test` + `nx lint`: `platform-feature-agencies`, `shared-data-access` | 16 + 53 pass, lint clean |
| Live HTTP walkthrough against a local backend | see TASKS.md task 6 |

## Not verified

- The Create-agency and setup-link drawers in a real browser (visual layout,
  clipboard fallback on an insecure origin, the "issue a license" link).
- Deployment of migration `d5b9e3a7f1c4` to the production droplet.

## Known limitations (also in ADR-048)

- The setup link is returned in the response because email delivery is not
  configured; `LoggingEmailSender` also writes the raw token to the server log.
- No subdomain routing yet: the agency code is validated as a DNS label but
  nothing resolves it.
- No authenticated change-password endpoint exists.

Design: [PLAN.md](./PLAN.md). Tasks: [TASKS.md](./TASKS.md). Decision: ADR-048.
