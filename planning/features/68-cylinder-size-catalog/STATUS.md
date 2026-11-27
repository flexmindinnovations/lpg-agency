# 68 — Status

**2026-11-26 — Built and checked. Merged in PR #218 and deployed 2026-11-27.**

## Checks

- Backend: `ruff check`, `ruff format --check`, `mypy` (670 files),
  `import-linter` (7 contracts) and the OpenAPI check pass; 1,829 unit tests
  pass.
- Database: all 599 integration tests pass on a temporary database set up as
  in CI. Many test files name `lpg_test` directly, so they were run from a
  copy pointed at the temporary database.
- Dashboard: tests and lint pass for every project except `dashboard-e2e`,
  and the production build succeeds. Its budget warnings are not about files
  changed here.
- Screens: checked in a headless browser with every API call faked (dark,
  light and phone). Nothing was sent to the live server.
- The end-to-end test was not run; only its cylinder name changed.
- The demo seed script ran twice on a new local database. It crashed while
  printing the demo logins, a fault already on `main`; fixed. On a database
  seeded before this change, running it again would add the new names beside
  the old types.
- Real run: this branch's backend and dashboard on a new local database with
  demo data (`127.0.0.1:4300`). Signed in, added, resized and deleted a type,
  and confirmed a type in use cannot be deleted. No failed API calls.

## After deployment

The dashboard on `localhost:4200` calls the live server, so the new screen
works only once this is deployed. Records typed before the list are flagged on
the Cylinder Types screen; open each one and choose its size.
