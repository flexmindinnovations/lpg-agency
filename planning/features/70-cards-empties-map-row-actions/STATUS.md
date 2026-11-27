# 70 — Status

**2026-11-27 — Built and checked. Not committed, merged or deployed.**

## Checks

- Backend: `ruff`, `ruff format --check`, `mypy`, `lint-imports`, OpenAPI
  `--check` pass. Full suite on a throwaway database: 2458 passed, 6 skipped,
  11 failed. The 11 are `.env`-file tests and failed only because the throwaway
  copy has no `.env` files; those three test files pass in the real folder
  (43 passed).
- Dashboard: test and lint (33 projects), e2e lint and build pass. The three
  size-budget warnings are older than this change.
- Flutter: tests pass for `driver_app`, `customer_app`, `api_client` and `maps`;
  analyze is clean for those and `admin_app`.
- Browser, every API call faked: section cards on 13 pages and 10 drawers
  (drawers also at phone width), row actions on the tables, tooltips on hover
  and keyboard focus.
- The Driver app screens were checked by widget tests, including a 320 px wide
  one. They were **not** run on a phone or emulator.

## Found and fixed while checking

- Row action buttons sat 9 px above the centre of their rows.
- Drawers opened from Settings pages lost their card borders (Settings shows its
  own cards flat, and the drawer inherited that).
- The customer drawer's tab content was indented from the card above it.
- The cylinder type drawer's details were not in a card.
- A long section heading on the delivery screen could overflow a narrow screen.

## Before release

- Run migration `f5c8d1a4b926`.
- Ship the new Driver APK with the backend. The old one fills "Empties
  collected" with the number ordered, which the server now refuses for a
  customer holding fewer.
- Customers who held cylinders before this software show 0 empties until the
  office corrects the balance on the Ledger page.
