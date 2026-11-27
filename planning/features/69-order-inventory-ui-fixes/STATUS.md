# 69 — Status

**2026-11-27 — Built and checked. Not committed, merged or deployed.**

## Checks

- Dashboard: 684 unit tests pass; lint passes for every project; the
  production build succeeds with only the three size-budget warnings.
- Backend: `ruff check`, `ruff format --check`, `mypy` (673 files),
  `import-linter` (7 contracts) and the OpenAPI check pass; 1,848 unit tests
  pass.
- Database: the full suite on a temporary database gave 2,446 passed, 6
  skipped and 11 failed. The failures came from how that copy was set up (no
  `.env.*` files, an extra database setting); those three test files pass in
  the real folder (43 of 43). The new booked-order estimate test passed.
- Screens: 29 checks in a headless browser with every API call faked (dark and
  light, plus a phone-width booking): no error toasts, no writes, nothing sent
  to the live server. Action buttons measure at least 4.8:1 contrast.
- The end-to-end workflow test was updated for the new customer dropdown but
  not run.

## Notes

- The grey button style is not used for row actions: in dark mode it measured
  3.9:1, under the WCAG 2.2 AA minimum.
- Dropdowns fed by a capped list (up to 200 entries) search what is loaded.
  The table page-size picker is part of AG Grid and has no search.
- Linked Devices still scrolls sideways to reach Actions at 1366px wide, as it
  did before.

## After deployment

The dashboard on `localhost:4200` calls the live server, so the price estimate
appears there only once the backend is deployed. The other changes show now.
