# Status: linked device delete and stable test signing

**Done** (2026-11-08), on branch `claude/linked-device-reinstall`. See PLAN.md for the finding and ADR-073 for the decision.

## Verified
- Backend: ruff, ruff format, `mypy --strict`, import-linter (7 contracts kept); 1,704 unit tests pass; 46 device integration tests pass on a freshly migrated database, including delete, audit entry, RBAC (manager gets 403) and another agency's phone (404, and a raw `DELETE` as `lpg_app` removes 0 rows).
- OpenAPI spec regenerated with the project's locked environment (only the new endpoint differs); dashboard client regenerated.
- Dashboard: tests, lint and a production build pass for `shared-ui`, `shared-data-access`, `admin-feature-license` and the dashboard app.
- Signing: Admin and Driver release APKs built locally carry the internal-test certificate (SHA-256 `66807e4f...6cbda1517`).

## Not verified
- The Delete button in a running dashboard against a real backend (production does not have the endpoint until this is deployed), and a real reinstall across two CI builds on a phone.

## After deploy
- Run the migration (`alembic upgrade head`) on each environment before using Delete.
- Uninstall the Admin and Driver apps once, then install the next APK built from this change; later builds update in place and keep the phone's record.
- Delete the existing duplicate rows from Linked Devices.
