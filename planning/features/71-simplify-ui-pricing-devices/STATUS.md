# 71 — Status

**2026-11-27 — Built and checked. Not committed, merged or deployed.**

## Checks

- Dashboard: tests and lint pass for all projects, with no lint warnings; the
  build passes (3 size-budget warnings that were there before); e2e lint
  passes.
- Backend: `ruff`, format, `mypy --strict`, `lint-imports`, the OpenAPI check
  and 1869 unit tests pass.
- Backend with a database, on a throwaway copy: everything passes except 11
  tests that read `.env` files, which the copy leaves out. Their three files
  pass in the real folder.
- Browser, with every API call faked, in dark, light and at phone width:
  invoice drawer, order quick view, Cylinders & Prices and its drawers, Linked
  Devices and its drawer, audit log, Razorpay keys, Agency, cash book. Row
  action buttons measured on Branches, Godowns, Users, Employees and Linked
  Devices.
- Found by the browser checks and fixed: the invoice drawer was wider than a
  phone screen.
- Not seen in a browser: the customer onboarding review step and the facts on a
  compliance document. Their change is the shared label-and-value class.
- Not tried against a real phone: that a Driver or Admin app sign-in appears in
  Linked Devices. Server tests cover it.

## Follow-up, 2026-11-27

- Dashboard tests, lint (no warnings), build and e2e lint pass. No backend
  change.
- Browser, with every API call faked, in dark, light and at phone width: audit
  entry, cylinder drawer with the older server's answer, Branch Details, a table
  inside a card, and a table header with rows scrolled under it. The earlier
  browser checks for this feature and for section cards were run again and pass.

## Second follow-up, 2026-11-27

- Dashboard tests, lint (no warnings), build and e2e lint pass. No backend
  change.
- Browser, with every API call faked: heading-line buttons, tables in cards,
  export buttons and the GST warning. A scan of section cards on the pages and
  drawers in the check found no line with nothing under it.
- **Open, owner and accountant:** confirm the GST rate of each cylinder.
  Changing a rate does not change confirmed orders or issued invoices, and the
  app cannot raise a debit note.

## Tables in cards, 2026-11-28

- AG Grid drew a second frame inside each table, so tables in cards still showed
  side and bottom lines after the second follow-up. That check had measured only
  the table's outer box. The inner frame is off, and the new check reads every
  element along a table's edges.
- **Scroll lag when zoomed in:** measured, not fixed. In a 100-row table each
  wheel step ran about 10 ms of script in a production build, with pauses of up
  to about 40 ms; without the chips, links and buttons in cells it was about
  half. The page background and the grid settings made no clear difference. Lag
  on a table of a few rows was not reproduced.

## Release notes

- No new migration. Release dashboard and backend together: without the new
  `delete_blocked_by` field the cylinder drawer also counts a price as a
  reason not to delete.
- A local dashboard that proxies to the hosted server shows the old server
  behaviour until the backend is deployed.
- Phones appear at their next sign-in or session refresh. They are now recorded
  for every agency. ADR-071 asks for a notice in the apps and a retention
  period; no such notice text was found in the mobile code, and the legal
  wording needs the agency's adviser.
