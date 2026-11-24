# Status — 67 module visibility

2026-11-24 — Implemented, awaiting deploy and end-to-end check.

Backend and dashboard are done; lint, `mypy --strict`, `import-linter`, backend unit tests and frontend
tests pass. Not run: Postgres integration tests (no local database) and the browser check against a
backend that has the new endpoints (the dev server proxies to the droplet, which does not yet).
