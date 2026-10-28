# 49 - Admin app: drivers and vans

**Why:** the admin app could send an order out, but could not create the drivers and vans the trip sheet needs. "No free driver in this branch" was a true empty list with no way to fix it from the phone.

## What shipped
- Drivers and vans area (Dispatch tab, top-right icon; also offered from the Send out sheet when a picker is empty). Lists, add, manage.
- Add driver, same rules as the dashboard: a driver employee (new, or an existing driver-role employee without a profile), then the driver profile with a required licence photo (OCR prefills number and expiry), then the Driver App login. A retry after a partial failure reuses the employee that was already created.
- Add van: registration, make, model, ownership, capacity, required RC photo and expiry (OCR prefill).
- Manage: driver licence update, active / on leave / inactive; van details, active / maintenance / inactive. Inactive is final (server rule), so it asks first. Enable Driver App login from the driver page.
- Dispatch: a banner when no driver or van is active, why the pickers are empty (nobody registered, other branch, all on trips, none active), cancel trip (planned or loaded), past trips view.

## Not in the app yet
- Settling a finished trip (needs an approved van reconciliation, which has no inventory screens here), trip detail with weighment and cash handover, stop re-ordering, delivery photo and signature capture by staff.
- Changing a driver's branch or linked employee (dashboard-only structural change).
