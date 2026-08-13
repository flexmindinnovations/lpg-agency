# Phase 9 — Driver Management

## Goal

Implement Driver and Vehicle management across the backend and Angular dashboard.  
Driver and Vehicle are independent aggregate roots in the `delivery` bounded context.

## Scope

- **Backend:** `delivery` schema migration, domain aggregates, application use cases,
  infrastructure repositories, FastAPI router, permission seeding.
- **Frontend:** Angular lazy-loaded `feature-drivers` and `feature-vehicles` libraries,
  AG Grid lists, PrimeNG dialog detail/create forms, sidebar nav links.
- **Tests:** unit (domain + use cases), integration (repository RLS, smoke, RBAC).

## Out of Scope for this Phase

- Route planning (Phase 10+).
- Vehicle–InventoryLocation linking (Phase 10+).
- Mobile (Driver App) delivery workflow (Phase 11+).

## References

- `docs/data/01-domain-model.md` §4.9 (Driver), §4.10 (Vehicle)
- `docs/data/03-database-schema.md` Schema: `delivery`
- `docs/data/17-api-security.md` §6 Permission Matrix
