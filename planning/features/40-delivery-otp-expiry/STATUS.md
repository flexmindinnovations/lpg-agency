# 40 — Delivery code expiry — Status

**2026-10-19 — Done.** Gates run locally: backend ruff, ruff format, mypy
--strict, import-linter, OpenAPI drift check and the unit suite pass. Flutter
3.47: `dart format`, `flutter analyze` and `flutter test` pass for
`design_system`, `api_client`, `driver_app` and `customer_app`. The order smoke
test's new resend step needs the docker-compose PostgreSQL and was not run
here. Not yet run on a device.
