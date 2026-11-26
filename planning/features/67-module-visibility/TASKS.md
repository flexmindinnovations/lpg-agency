# Tasks — 67 module visibility

- [x] Domain module catalog (`domain/license/modules.py`)
- [x] Migration + model + repository (`platform.tenant_module_setting`, RLS) — migration SQL reviewed offline
- [x] Use cases: list / set (`application/license/module_access.py`)
- [x] `require_module` dependency on `/ai`, `/scales`, `/cylinder-units` (403 `MODULE_DISABLED`)
- [x] `GET /admin/modules`, `GET/PUT /platform/agencies/{id}/modules[/{key}]`; OpenAPI and client regenerated
- [x] Backend unit tests (6)
- [ ] Backend integration + tenant-isolation test against Postgres (no Postgres available locally; run in CI)
- [x] Dashboard: `ModuleAccessStore`, `moduleGuard`, sidebar + command-palette filtering
- [x] Platform Console: Modules switches in the agency details drawer
- [x] Platform Console: module switches moved into a "Manage modules" dialog; the drawer shows only an "N of M on" summary so the agency details stay visible. Escape closes the dialog first, then the drawer (component and page tests)
- [x] Frontend tests (store, guard)
- [ ] Verify end to end after deploy (switch a module off, confirm hidden, URL redirects, API 403)

## Discovered, not done
- Weighment endpoints (`/goods-receipt-notes/*/weighment`, `/routes/*/weighment`) stay open: they are part of receiving and dispatch, not the Scales module screens.
- The mobile apps do not hide modules; they would receive 403 from the API.
- Migration `c5a8f2d1b9e7` chains from `b3e6d1f8a427`; if another migration lands first, re-point `down_revision`.
