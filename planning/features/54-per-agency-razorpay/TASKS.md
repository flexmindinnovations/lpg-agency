# Tasks

- [x] Migration: `payment_gateway_credential` table, RLS, token resolver function
- [x] Application: credential use cases (get / set / remove / rotate), masking, mode
- [x] Infrastructure: encrypted repository, gateway resolver with platform fallback, tenant resolver
- [x] API: `/payment-gateway` endpoints, per-agency webhook route, gateway dependency per tenant
- [x] WhatsApp job resolves the agency's gateway
- [x] Audit: redact `*_encrypted` columns, label for the record
- [x] Tests: unit (use cases, resolution, webhook route) and integration (real Postgres: ciphertext at rest, audit, RLS, webhook, availability)
- [x] OpenAPI + Angular client; Settings > Online Payments page and spec
- [x] Docs: ADR-067, payment-flow, production checklist, integrations.env.example note
- [ ] Follow-up: agency admin app screen for the key (dashboard only for now)
- [ ] Follow-up: remember which account created each payment link so refresh survives a key change
