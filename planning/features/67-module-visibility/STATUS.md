# Status — 67 module visibility

2026-11-24 — Implemented, awaiting deploy and end-to-end check.

Backend and dashboard are done; lint, `mypy --strict`, `import-linter`, backend unit tests and frontend
tests pass. Not run: Postgres integration tests (no local database) and the browser check against a
backend that has the new endpoints (the dev server proxies to the droplet, which does not yet).

2026-11-25 — Fixed the agency details drawer: the inline module list squeezed the details out of view.
Modules now open in a dialog. Checked in the browser against the hosted API at 1440px and 375px (no
switches changed); Jest (28), ESLint, Prettier and the type-check pass for `feature-agencies`.
The dialog then looked grey with squashed switches. Fixed app-wide in `styles.css`: dialogs use the
same near-solid surface as drawers (no blur), their footer paints no separate background, and toggle
switches no longer shrink. Checked on the modules dialog in light and dark.

**2026-11-25 (screens that use another module):** with Scales off, Dispatch still loaded the scales list and showed the server refusal as a toast. The rule now: a screen that uses a module it does not require checks `ModuleAccessStore.isEnabled`, does not call that API and hides the related controls.
- Applied to: Dispatch (Scales, Inventory, Cash Handovers), order detail (Dispatch, Drivers, Vehicles, Inventory, Invoices), Inventory (Vehicles, Scales), Complaints (Customers, Orders), cylinder units (Vehicles, Customers), Customers (Orders), Employees (Drivers), compliance calendar (Drivers, Vehicles), driver and vehicle documents (Compliance Calendar) and the command palette.
- Safety net: `AppErrorHandler` no longer toasts a `MODULE_DISABLED` from a background load. Refused changes are still toasted.
- Not changed: Home still calls the report, cash, reorder, rating and refill endpoints and hides the cards that are refused (no toast, but 403s in the console).
- Checked: unit tests (new cases for Dispatch, Employees, command palette, error handler), lint, type check, build; each screen opened in headless Chromium with only its required modules on and a fake API: no calls into an off module except Home.
- **Open, needs a product decision (backend catalog unchanged):** with only the modules the catalog requires, some work cannot finish. Dispatch without Inventory: no stock can be received to load, and a trip cannot be settled (needs an approved reconciliation). `weighment_gate_enabled` without Scales: trips cannot be loaded. Orders without Dispatch: no Send out. Complaints without Customers: none can be raised. Drivers or Vehicles without Compliance Calendar: documents cannot be verified or replaced.

**2026-11-26 (modules dialog):** every switch flashed when one was changed, because all of them were disabled while it saved, and each flip was its own request.
- The dialog now keeps changes until **Save changes** and sends them in one request. Cancel, close and Escape drop them. A refused save keeps them in the open dialog.
- API: `PUT /platform/agencies/{id}/modules` with `{"modules": {key: bool}}` replaces `PUT .../modules/{module_key}`. It checks dependencies on the result and saves all changes in one transaction, or none.
- One "All modules" switch replaces the Turn all on / Turn all off buttons. It is on only when every module is on, so from a mixed state one flip turns the rest on and a second turns all off.
- Fixed on the way: error bodies of calls that return nothing arrived as text, so toasts showed the raw HTTP line instead of the server's message (`problem-details.ts`).
- Checked: backend lint, types, boundaries, OpenAPI export and unit tests; frontend tests, lint and build; headless Chromium with a fake API (dark, light, phone). The two new database tests were not run locally (no PostgreSQL). No live data was changed.
- **Dialog jumped while in use:** the close button was removed during a save, dependency notes came and went with the switches (resizing and recentring the dialog), and the footer wrapped on phones. The notes are now fixed text ("Needs …", "Needed by …"), the close button stays (closing during a save lets it finish), and the footer keeps its height. Checked frame by frame at four screen sizes.
