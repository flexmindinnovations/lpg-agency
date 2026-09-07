# Regulatory & MDG Compliance — Status

## Current Status

- **State:** 🔵 **NOT STARTED** — `PLAN.md`'s own scope (weighment capture, TDT clock + star-rating dashboard, record-retention/OMC inspection pack, compliance calendar, DAC-in-POD, filled-vs-empty reconciliation, PAHAL/PMUY subsidy, cash/UPI settlement) is still planned only, not built.
- **Created:** 2026-08-18

## Exception: D24 — Driver/Vehicle Compliance Document Pack — 🟢 DONE

One item from `PLAN.md`'s backlog (row 4, "Compliance calendar... vehicle docs", tracing to `docs/research/feature-gap-analysis.md` **D24** — "Vehicle/driver compliance pack: hazmat licence endorsement, TREM card, fitness, PUC, insurance, refresher-training expiry") was pulled forward and built as its own narrower, self-contained feature, independent of the rest of this file's PLAN.md scope. Gates re-run and green, not assumed:

- **Domain/persistence/API** (`953f41e`, `16337f4`, `e19c33e`, `fd2ccaf`): standalone `ComplianceDocument` aggregate (ADR-038), `delivery.compliance_document` table with RLS, add/replace/verify/list use cases and endpoints, driver/vehicle registration now a two-step upload-then-register flow that creates the owner's required document (`driving_licence` / `vehicle_rc`) in the same transaction as the owner itself.
- **Dashboard** (`0dcd374`): shared `lpg-compliance-documents-panel` in both the Driver and Vehicle detail drawers (table, add/replace inline form, verify/reject gated by `compliance:verify`), plus an Expiry filter (`all | expiring ≤30d | expired | missing required`) on both list pages. Live-verified in-browser: added a document through the real upload → MinIO → `compliance_document` row path, verified it, and confirmed the "missing required" filter correctly flagged drivers with no `driving_licence` on file.
- **Nightly notification cron** (`a30f4e1`): `check_compliance_expiry`, registered at 3:00 AM, resolves each tenant's `compliance_expiry_lead_days` `TenantConfiguration` (default 30 days) and enqueues one in-app `compliance_document_expiring_staff` notification per expiring/expired document, deduped via `last_expiry_notified_at`. Live-verified end-to-end against the dev DB/Redis: inserted a document expiring in 10 days, ran the cron, drained the queue with `arq ... --burst`, and confirmed all 3 ops-staff accounts received the notification with correct content. Test data removed afterward.
- **Gates:** targeted + full-repo `ruff check` / `mypy` clean on every touched file; all existing unit + integration suites for compliance documents, notification jobs, and tenant configuration pass (`uv run pytest tests/unit/test_compliance_document.py tests/integration/test_compliance_document_repository.py tests/integration/test_compliance_document_endpoints_smoke.py tests/integration/test_tenant_configuration_repository.py tests/unit/test_domain_tenant_configuration.py tests/unit/test_infrastructure_notification_jobs.py` — 44 passed); `frontend` lint/build/test all clean for the touched libs.

**This does not move the file's own `State` above off NOT STARTED** — D24 was one line item out of the much larger PLAN.md backlog, and every other row in that backlog (weighment, TDT, record retention, compliance calendar's other document types, DAC, subsidy/settlement) remains untouched.

## Rules

This file follows [`planning/MODULE_STATUS.md`](../../MODULE_STATUS.md): the `State` above moves off NOT STARTED only when *all* of `PLAN.md`'s gates are re-run and green, with the command output seen. Four phases in this project were marked COMPLETE here and then failed independent verification — that is why the bar is stated explicitly rather than assumed. D24's own gates above were independently re-run and are reported honestly as green; they cover D24 only, not the rest of this file's scope.

## Verification checklist

See the Verification section of `PLAN.md`. Nothing is checked off from a report; each item is re-run.
