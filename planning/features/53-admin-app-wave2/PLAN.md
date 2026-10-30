# 53 — Admin app Wave 2: compliance alerts, pricing, employees, users and roles

## Why
Wave 1 (52) gave the owner the daily work on a phone. What still forces a trip to the web dashboard is the less frequent but costly work: a licence or insurance that lapses unnoticed, a price change, adding a driver's employee record, giving someone access.

## Decisions
- **Order (value first, risk last):** 1 Compliance alerts, 2 Pricing, 3 Employees, 4 Users and roles. Users and roles is last because it is the most sensitive and its permission matrix does not fit a phone screen; the phone gets list, invite, change role, deactivate/reactivate, and the per-user permission overrides stay on the web.
- Same backend, endpoints and RBAC as the dashboard; no backend change unless a gap is found (recorded in TASKS).
- Pickers: dropdowns for 4+ options or data-driven lists, chips only for 2 or 3 (see 52 STATUS, "Pickers").
- Each module ends with analyze + tests green, a run on the emulator, planning docs updated and a PR stacked on the previous one.

## Modules
1. **Compliance alerts** — `GET /compliance-documents?expiry=upcoming` (drivers:read): everything overdue or due within 90 days across drivers, vans, godowns and the agency; open one, see its number, dates and verification state; **renew** it (new photo, number, expiry via `PUT /compliance-documents/{id}`, drivers:manage). Dashboard attention card and More badge. Verify/reject (compliance:verify) stays on the web.
2. **Pricing** — price list per cylinder type and customer type, set a price, review price proposals.
3. **Employees** — list, register, edit, change status, enable app login.
4. **Users and roles** — staff list, invite, change role, deactivate/reactivate.

## Risks
- Renewal needs a photo upload from the phone; the existing fleet document field is built around OCR for licences and RCs, so it is made usable without OCR.
- A document's owner is an id; names come from the driver, van and godown lists already loaded for fleet.
