# 39 — Optional delivery signature and photo — Status

**2026-10-19 — Done, in review.** Drivers can confirm a delivery without the
customer's signature and/or a delivery photo; the OTP and GPS still gate it.
Gates run locally: backend ruff, ruff format, mypy --strict, import-linter,
OpenAPI drift check and the full pytest suite pass; the migration was run up,
down and up again against PostgreSQL 16. Flutter: `dart format`, `flutter
analyze` and `flutter test` pass for `api_client`, `sync_engine` and
`driver_app`. Not yet run on a device.
