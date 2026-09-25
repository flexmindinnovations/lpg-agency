# Tasks: Agency Provisioning

- [x] 1. Domain: `Tenant.provision()` + slug/reserved-word/email validation + `TenantProvisioned` event; unit tests (37 pass in `test_domain_tenant.py`)
- [x] 2. Migration `d5b9e3a7f1c4`: `tenant.tenant_provision(...)` SECURITY DEFINER function + grant; `TenantRepository.add()` (writes its own audit row); applied to the local test and dev databases
- [x] 3. Application: `InviteStaffUserUseCase.invite()` (returns raw token; `execute()` unchanged); `ProvisionTenantUseCase`; 6 unit tests with fakes
- [x] 4. API: `POST /platform/agencies` + schemas + import-linter exemption + OpenAPI re-exported; 6 integration tests (`test_platform_agency_provisioning.py`: happy path, hash-only token, audit row, duplicate slug/email, compensation) pass against real PostgreSQL
- [x] 5. Frontend: client regenerated; Create-agency drawer + one-time setup-link drawer; 16 component tests + shared data-access suite pass, lint clean
- [x] 6. Live verification (backend, over real HTTP against the local stack): create → 409 duplicate slug/email, 409 reserved code, 422 bad code, 401 no token → set password via link → link is single-use (410) → login blocked `LICENSE_NOT_ACTIVATED` → issue + activate license → login as `agency_admin` (56 permissions) → 403 on `/platform/*`. **Browser check of the UI drawers is still open.**
- [x] 7. Docs: ADR-048, `planning/MODULE_STATUS.md` row 26, this file, `infrastructure/deploy/DEPLOY.md` note

## Deferred (discovered, not built)

- Issue + activate a license in the same call (existing endpoints cover it; revisit if the two-step flow proves clumsy)
- Subdomain-per-agency routing, Host-header tenant resolution, wildcard/on-demand TLS
- Email delivery of the setup link (needs an email provider; `LoggingEmailSender` also logs the raw token — see ADR-048)
- Authenticated change-password endpoint (none exists today)
