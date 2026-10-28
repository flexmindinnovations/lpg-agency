# 49 - Admin app: drivers and vans

**Why:** the admin app could send an order out, but could not create the drivers and vans the trip sheet needs. "No free driver in this branch" was a true empty list with no way to fix it from the phone.

## What shipped
- Drivers and vans area (Dispatch tab, top-right icon; also offered from the Send out sheet when a picker is empty). Lists, add, manage.
- Add driver, same rules as the dashboard: a driver employee (new, or an existing driver-role employee without a profile), then the driver profile with a required licence photo (OCR prefills number and expiry), then the Driver App login. A retry after a partial failure reuses the employee that was already created.
- Add van: registration, make, model, ownership, capacity, required RC photo and expiry (OCR prefill).
- Manage: driver licence update, active / on leave / inactive; van details, active / maintenance / inactive. Inactive is final (server rule), so it asks first. Enable Driver App login from the driver page.
- Dispatch: a banner when no driver or van is active, why the pickers are empty (nobody registered, other branch, all on trips, none active), cancel trip (planned or loaded), past trips view.

## Follow-up: trips end to end
- Trip detail (tap a trip on Dispatch): driver and van, stops in order, van load, weight checks, and a read-only cash line (cash to collect, handover declared). Cash declaring and review stay in the cash handover flow.
- Re-order stops (`POST /routes/{id}/optimize`, per-agency switch) and cancel trip.
- Settle trip: tries `POST /routes/{id}/reconcile`; if the van has no approved count it takes the count (every cylinder type and status on the van, prefilled with the expected figure), approves it, then settles. A count recorded by someone else is approved instead of counted twice. Self-approval follows the server rule (admins only), so a non-admin counter gets a clear message.
- Record delivery from the office takes the optional customer signature and delivery photo, like the Driver App.
- Change a driver's branch (`PATCH /drivers/{id}/assignment`, same employee, as the dashboard does).

## Not in the app yet
- Cash handover redesign (bank details, QR, UPI, Razorpay) is a separate piece of work.
