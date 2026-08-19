# Phase 17: Complaint Management Tasks

> Backfilled 2026-08-19 (R8) — the feature shipped without this file ever
> being created; the checklist below reflects what was actually built,
> reconstructed from the code and from R7/R10's fix history.

- [x] 1. Implement Domain Layer (`backend/src/lpg/domain/complaint/complaint.py`, `value_objects.py`) — `Complaint` aggregate, `ComplaintAssignment`/`ComplaintResolution` entities, SLA-by-priority calculation
- [x] 2. Implement Application Layer Use Cases (`RaiseComplaintUseCase`, `AssignComplaintUseCase`, `ResolveComplaintUseCase`)
- [x] 3. Implement Infrastructure Layer (`SqlAlchemyComplaintRepository`, `models/complaint.py`)
- [x] 4. Generate Alembic migrations (`4e7fc25f58b3` schema+tables+RLS, `b05967dbc83e` `complaints.manage` permission code)
- [x] 5. Implement API Layer (`routers/complaint.py`)
- [x] 6. Implement Frontend (`@lpg/complaint/feature-complaints` library)
- [x] 7. Wire `/complaints` route into dashboard `app.routes.ts`
- [x] 8. (R7, 2026-08-19) Add domain/use-case/integration test coverage — zero existed before; found and fixed 3 real backend bugs in the process (broken `TenantResolver` wiring crashing every mutation endpoint, `.id` `AttributeError` on both entities, a `MissingGreenlet` crash from a stale `AsyncSession` identity-map read in `save()`)
- [x] 9. (R10, 2026-08-19) Add `ComplaintRaised`/`ComplaintResolved` domain events; fixed a dead event-dispatch path (`session.info["domain_events"]` was written but never read) so they actually reach the Unit of Work's dispatcher
- [x] 10. (R8, 2026-08-19) Backfill this planning directory
