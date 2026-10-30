# Status

Branch `feat/admin-app-compliance-alerts`, 2026-10-30, stacked on `feat/admin-app-stock` (PR #84, which stacks on #83 and #82; none merged yet). Wave 2 started; C1 Compliance alerts built, C2 to C4 not started.

## C1 Compliance alerts
Built on `GET /compliance-documents?expiry=upcoming` and `PUT /compliance-documents/{id}`; no backend change. Shown as More > Licences and papers (badge = lapsed or due within 30 days) and a dashboard attention card ("N licences or papers need renewing").
Tried on the emulator against the local backend, with four documents seeded through the API (a dev-only step, since the dev data had nothing expiring): the list grouped Expired / Due within 30 days / Due within 90 days with the right owner for a van, a godown and a driver; the document sheet; and a full renewal (photo from the gallery, new number, expiry typed as 29 Oct 2027), after which the expired insurance left the list. The dashboard card and badge counted the two remaining within 30 days.
Not tried: a renewal with the camera, renewing a document that carries no expiry (TREM card), the rejected-document banner, and a role without `drivers:read` / `drivers:manage` (the badge then reads 0 and the list shows the permission message).
Verify/reject stays on the web (`compliance:verify`).
