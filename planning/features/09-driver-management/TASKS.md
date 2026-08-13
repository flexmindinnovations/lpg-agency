# Phase 9 — Driver Management Tasks

- [x] Step 1: Planning docs
  - [x] Create PLAN.md
  - [x] Create TASKS.md (this file)
  - [x] Create STATUS.md

- [x] Step 2: Database Migration
  - [x] Create Alembic migration: delivery schema, driver + vehicle tables, RLS, permissions

- [x] Step 3: Domain Layer
  - [x] domain/delivery/__init__.py
  - [x] domain/delivery/driver.py (Driver aggregate, events, invariants)
  - [x] domain/delivery/vehicle.py (Vehicle aggregate, events, invariants)

- [x] Step 4: Application Layer
  - [x] application/delivery/__init__.py
  - [x] application/delivery/ports.py (DriverRepository, VehicleRepository protocols)
  - [x] application/delivery/use_cases.py (all commands and query use cases)

- [x] Step 5: Infrastructure Layer
  - [x] infrastructure/persistence/models/delivery.py (DriverModel, VehicleModel)
  - [x] Register models in Base metadata
  - [x] infrastructure/persistence/repositories/driver.py
  - [x] infrastructure/persistence/repositories/vehicle.py

- [x] Step 6: API Layer
  - [x] api/v1/schemas/delivery.py
  - [x] api/v1/dependencies/delivery.py
  - [x] api/v1/routers/delivery.py
  - [x] Mount delivery router in app.py

- [x] Step 7: Tests — Backend
  - [x] tests/unit/test_domain_driver.py
  - [x] tests/unit/test_domain_vehicle.py
  - [x] tests/unit/test_driver_use_cases.py
  - [x] tests/integration/test_driver_endpoints_smoke.py
  - [x] tests/integration/test_driver_rbac.py

- [x] Step 8: Backend Quality Gates
  - [x] pytest passes (all tests)
  - [x] ruff check/format passes
  - [x] mypy passes
  - [x] import-linter passes

- [x] Step 9: OpenAPI Regeneration
  - [x] export_openapi.py
  - [x] ng-openapi-gen regenerates Angular client

- [x] Step 10: Frontend
  - [x] Create libs/delivery/ Nx library group
  - [x] feature-drivers: list component + registration modal + status modal
  - [x] feature-vehicles: list component + registration modal + status modal
  - [x] Wire routes in app.routes.ts
  - [x] Add sidebar nav links in ShellLayout

- [x] Step 11: Frontend Quality Gates
  - [x] nx test dashboard passes (13/13 projects pass)
  - [x] nx build dashboard --configuration=production passes

- [x] Step 12: Documentation
  - [x] Update STATUS.md
  - [x] Update planning/current_phase.md
  - [x] Update knowledge/12-current-status.md
