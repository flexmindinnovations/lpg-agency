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
