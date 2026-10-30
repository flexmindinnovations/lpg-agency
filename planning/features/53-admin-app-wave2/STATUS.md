# Status

Branch `feat/admin-app-pricing` (on top of `feat/admin-app-compliance-alerts`, PR #85), 2026-10-30, stacked on `feat/admin-app-stock` (PR #84, which stacks on #83 and #82; none merged yet). Wave 2 started; C1 Compliance alerts and C2 Pricing built, C3 and C4 not started.

## C1 Compliance alerts
Built on `GET /compliance-documents?expiry=upcoming` and `PUT /compliance-documents/{id}`; no backend change. Shown as More > Licences and papers (badge = lapsed or due within 30 days) and a dashboard attention card ("N licences or papers need renewing").
Tried on the emulator against the local backend, with four documents seeded through the API (a dev-only step, since the dev data had nothing expiring): the list grouped Expired / Due within 30 days / Due within 90 days with the right owner for a van, a godown and a driver; the document sheet; and a full renewal (photo from the gallery, new number, expiry typed as 29 Oct 2027), after which the expired insurance left the list. The dashboard card and badge counted the two remaining within 30 days.
Not tried: a renewal with the camera, renewing a document that carries no expiry (TREM card), the rejected-document banner, and a role without `drivers:read` / `drivers:manage` (the badge then reads 0 and the list shows the permission message).
Verify/reject stays on the web (`compliance:verify`).

## C2 Pricing
Built on `GET/POST /admin/price-list` and `GET/PATCH /admin/price-list/proposals`; no backend change. More > Pricing lists the price in force for each cylinder type and customer type (and branch), with "Changes to ... on ..." when a later price is scheduled. Tap a row to change it (the sheet shows the earlier prices), or Add price for a new combination. Saving adds a newer price from now, so history is kept. A move of more than 25% asks "Change the price by +900%?" before saving. OMC rate changes waiting for review sit at the top, with Accept and Reject.
Tried on the emulator against the local backend: the list (5 cylinder types, domestic/commercial/industrial/government), the large-change check (9055 against 905.50, cancelled), a normal change to 910 and back to 905.50 (the dev price is restored; two extra history entries remain), the earlier-prices list, and the Add price sheet.
Found and fixed while testing: a price saved "now" showed as a scheduled change because the emulator clock runs about 1.5 s behind the server. The screen now allows 2 minutes of clock skew.
Not tried: accepting or rejecting a proposal (none on the dev data; widget tests cover the list, and the API tests cover the calls), saving a new combination, a role without `tenant:configure` (the proposals section is then hidden and saving shows the server message).
`dio` is now a direct dev dependency of admin_app (a test builds its own client).
