# Phase 17: Complaint Management Status

> Backfilled 2026-08-19 (R8). No PLAN/TASKS/STATUS ever existed for this
> phase before — it shipped, then C4 (`planning/MODULE_STATUS.md`) found it
> had zero test coverage, which R7 and R10 then closed out. This file
> documents the real, current, verified state — not a historical record of
> a plan that was followed, since no such plan was ever written down.

## Current Status
- **State:** ✅ **COMPLETE** — backend implemented, tested, and verified. Frontend implemented but not live-browser-verified in this pass.
- **Test coverage added:** 2026-08-19 (R7, R10)

## Backend — ✅ complete and independently verified

- [x] Domain model (`Complaint` aggregate, `ComplaintAssignment`/`ComplaintResolution` entities, SLA-by-priority calculation)
- [x] Application use cases (raise, assign, resolve)
- [x] Repository implementation
- [x] Alembic migrations (`4e7fc25f58b3`, `b05967dbc83e`)
- [x] REST API (`POST /complaints`, `POST /complaints/{id}/assign`, `POST /complaints/{id}/resolve`, `GET /complaints`, `GET /complaints/{id}`)
- [x] Domain events (`ComplaintRaised`, `ComplaintResolved`) — added R10, no subscriber yet
- [x] Gates: ruff, mypy, all 5 import-linter contracts, full unit + integration suites green
- [x] Domain unit tests (`test_domain_complaint.py`), use-case unit tests (`test_complaint_use_cases.py`), through-the-stack integration + RBAC tests (`test_complaint_endpoints_smoke.py`, `test_complaint_rbac.py`)

### Three real bugs found and fixed while adding test coverage (R7, 2026-08-19)

This phase had **zero tests** until R7 — C4 in `planning/MODULE_STATUS.md`
predicted exactly this class of module would be hiding real defects, and it
was right:

1. **Every `POST /complaints`, `/assign`, `/resolve` call crashed.** The
   router injected an already-resolved `AuthenticatedPrincipal` into a
   parameter typed and used as a `TenantResolver`, then called
   `.resolve(request)` on it — `AttributeError` on every real call. Fixed
   by having the three use cases accept an already-resolved `TenantContext`
   directly instead.
2. **`.id` raised `AttributeError`** on `ComplaintAssignment`/
   `ComplaintResolution` — both are `Entity` subclasses whose
   `@dataclass`-generated `__init__` never calls `Entity.__init__` or sets
   its `_id` slot. Broke `save()`'s assignment-merge lookup and response
   serialization alike. Fixed with an `.id` property reading `entity_id`.
3. **`MissingGreenlet` crash in `save()`**, even after fix #2.
   `session.get(ComplaintModel, complaint.id)` carried no loader options;
   `AsyncSession`'s identity map holds objects weakly, so the eagerly-loaded
   model from `get_by_id` could be collected before `save()` ran, leaving a
   freshly-refetched instance with unloaded relationships that then
   lazy-loaded outside any greenlet-bridged `await`. Fixed by passing the
   same `selectinload` options to `session.get(..., options=...)`.

### One more bug found and fixed while adding domain events (R10, 2026-08-19)

`SqlAlchemyComplaintRepository.save()` pushed events onto
`session.info["domain_events"]` — a mechanism nothing in the codebase ever
reads. `SqlAlchemyUnitOfWork.commit()` only collects from aggregates
registered via `register_aggregate()`. Every complaint event, from the very
first one ever recorded, was silently dropped at commit. Fixed by switching
the repository to the same `register_aggregate()` pattern every other
repository uses.

### A deliberately-undecided observation, not a bug

`GET /complaints` and `GET /complaints/{id}` carry no `require_permission`
dependency at all — any authenticated staff member of the tenant can read
complaints, regardless of role. `test_complaint_endpoints_smoke.py`
documents this as observed behavior
(`test_get_and_list_reachable_without_complaints_manage`) rather than
"fixing" it by guessing at an intended permission — nothing in the design
docs says this is wrong.

## Frontend — 🟡 implemented, not re-verified this pass

- [x] Nx library scaffolded (`@lpg/complaint/feature-complaints`)
- [x] Wired into `app.routes.ts`
- [ ] Component tests — pre-existing Jest/ESM transform gap (same class of
      issue tracked project-wide, not specific to this feature)
- [ ] Not live-browser-verified in this session (R7/R10 were backend-only
      passes)

## Completion Notes

1. This phase is a good example of the gap C4 was named for: "complete" and
   shipped, with a router and full domain logic, but genuinely zero tests —
   and three of the paths a test would exercise were completely broken.
2. SLA due-date computation is pure and deterministic (`_calculate_sla`),
   fully covered by parametrized unit tests across all four priorities.
3. No automated SLA-breach alerting exists — `ComplaintRaised`/
   `ComplaintResolved` are recorded and dispatched correctly (R10), but no
   handler subscribes to either yet. Building one is future work, not a
   defect in what's here.
