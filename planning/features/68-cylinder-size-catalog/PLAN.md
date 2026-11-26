# 68 — Standard cylinder sizes and a details drawer

## Why

An agency could type any cylinder name and weight. The owner wants only
industry sizes (2026-11-26), picked from a list; "Set GST" gone once GST is
set; and a drawer with a cylinder type's details, update and delete.

## Decisions

- **List:** the sizes IndianOil and HPCL publish (owner choice, 2026-11-26).
  Domestic: 5, 10 (composite), 14.2 kg. Commercial/industrial: 2, 5 (free
  trade), 19, 35, 47.5, 425 kg. BPCL's list was not checked. Private-brand
  sizes are not offered. Replaces D-04 (any size). Adding a size is a code
  change.
- **Name and weight** come from the list; each size once per agency.
- **No migration.** A record is on the list when its name and weight both
  match an entry.
- **Older records** (typed before this) stay usable and are flagged. One can
  take a list size of the same weight even when already used, since no
  quantity changes.
- **Size change:** otherwise only while nothing refers to the type.
- **Delete:** only while nothing refers to the type; otherwise deactivate. It
  is a soft delete, as the table's grants require (no `DELETE`).
- **GST:** the grid offers "Set GST" only while it is missing. Later changes
  are made in the drawer.

## Changes

- Backend: catalog in the domain; `GET /admin/cylinder-sizes`; create by
  `size_code`; `PATCH /admin/cylinder-types/{id}`; `GET .../{id}/usage`;
  `DELETE .../{id}`; the free-text rename and weight endpoints are removed
  (no screen or app called them).
- Dashboard: "Cylinder type" (domestic, or commercial and industrial) and
  size dropdowns, the type filtering the sizes (owner request, 2026-11-26);
  name link to a details drawer; flag for off-list records.
- Mobile apps: no change; they only read the list.
- Demo data and the end-to-end test use list names.

## Not in scope

- Refusing a domestic cylinder for a commercial customer, and choosing GST by
  customer type (audit TAX-1).
- Limiting GST rates to the current slabs (audit TAX-8).

## Tests

Domain rules, use cases over HTTP on a real database (including tenant
isolation), and the page's component tests.
