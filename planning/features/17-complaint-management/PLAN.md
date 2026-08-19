# Phase 17: Complaint Management Implementation Plan

## Goal
Give customers and staff a way to raise, triage, and close out service complaints (short delivery, damaged cylinder, billing dispute, driver conduct, late delivery) against a per-priority SLA clock, so nothing sits unhandled long enough to become an MDG irregularity.

## Scope
1. **Domain Layer**: `Complaint` aggregate root (category, priority, status, SLA due date computed at creation) with in-aggregate `ComplaintAssignment`/`ComplaintResolution` entities.
2. **Application Layer**: `RaiseComplaintUseCase`, `AssignComplaintUseCase`, `ResolveComplaintUseCase` — each takes an already-resolved `TenantContext` from the router (no independent tenant resolution).
3. **Infrastructure Layer**: `SqlAlchemyComplaintRepository`, `complaint` schema (`complaint`, `complaint_assignment`, `complaint_resolution` tables), standard RLS.
4. **API Layer**: `POST /complaints` (raise), `POST /complaints/{id}/assign`, `POST /complaints/{id}/resolve`, `GET /complaints`, `GET /complaints/{id}`.
5. **Frontend UI**: `@lpg/complaint/feature-complaints` — raise/assign/resolve flows off a complaints list.

## Integration points
- SLA due date is computed once, at raise time, from priority (Critical 4h / High 24h / Medium 48h / Low 72h) — no background SLA-breach detector exists yet (see STATUS.md).
- Publishes `ComplaintRaised`/`ComplaintResolved` (added Phase R10, 2026-08-19) for a future notification/escalation/reporting subscriber — none subscribes yet.

## Out of Scope
- Automated SLA-breach alerting/escalation (event exists, no subscriber built).
- Complaint reopening after resolution — `resolve()` is terminal; a rejected or resolved complaint cannot be reassigned.
