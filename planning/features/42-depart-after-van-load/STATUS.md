# 42 — No delivery before the van is loaded — Status

**2026-10-19 — Done.** Reproduced with the order smoke test against a local
PostgreSQL + Redis (depart on a `planned` route returned 200). Backend ruff,
ruff format, mypy --strict, import-linter, OpenAPI drift check and the full
test suite pass locally. Driver App needs a new APK for the stop-screen states;
the server gate works without it.
