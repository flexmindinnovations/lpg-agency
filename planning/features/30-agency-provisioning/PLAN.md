# Plan: Agency Provisioning (Super Admin "Create agency")

**Phase:** 30
**Status:** Planned 2026-09-25.

## Problem

The Platform Console (`/platform/*`, `super_admin`) can list, suspend,
reactivate, close and license agencies (tenants) but **cannot create one**.
`0242df1a3871`'s docstring is explicit that this was deliberate: tenant RLS
(`id = app.current_tenant_id`) makes an INSERT impossible through any
tenant-scoped connection, and provisioning was left as an "elevated/seed
operation". The only creation path today is `scripts/seed_dev_user.py`, which
embeds a well-known password and is dev-only. A production database therefore
has no way to get its first agency.

## Scope

`POST /platform/agencies` — one call that creates:

1. the `tenant.tenant` row (status `trial`), and
2. the agency's first `agency_admin` user (passwordless), plus a one-time
   password-setup token.

Out of scope (recorded in TASKS.md, not built): license issuance/activation
(existing `POST /platform/license*` endpoints — a tenant without an *activated*
license is `PENDING_ACTIVATION` and its users cannot log in, so the UI links
there after creation), subdomain routing / wildcard TLS (needs a domain;
separate ADR), email delivery (no provider is configured — `LoggingEmailSender`
only logs), default branches/warehouses/cylinder types (the agency admin
creates these through the existing admin screens).

## Request / response

`CreateAgencyRequest`

| Field | Rules |
|---|---|
| `name` | required, trimmed, 1–120 chars |
| `slug` | required, **lowercase** `a-z0-9-`, 3–40 chars, starts/ends alphanumeric, no `--`, not reserved (`www`, `api`, `app`, `admin`, `platform`, `mail`, `static`, `assets`); globally unique. It is also the future subdomain, so it must be a valid DNS label. |
| `primary_contact_email` | required, valid email |
| `country` | ISO-3166 alpha-2, default `IN` |
| `subscription_plan` | default `standard` |
| `admin_email` | required, valid email, globally unique in `identity.identity_user` |

`CreateAgencyResponse` (201): `tenant` (existing `TenantResponse`),
`admin_user_id`, `admin_email`, `setup_path` (`/reset-password?token=…`),
`setup_token_expires_at`. The raw token is returned **once**, never stored
(only its hash is) — the Super Admin relays it, because `LoggingEmailSender`
cannot deliver it.

Permission: existing `tenant:manage_platform`, live-checked (same tier as
suspend/close). Errors: 409 duplicate slug / admin email, 422 invalid input.

## Design

- **Domain.** `Tenant.provision(...)` factory: validates name/slug/email/
  country, sets status `trial`, records `TenantProvisioned`. Slug rules live in
  the domain (single source of truth), not the schema.
- **Persistence.** New `SECURITY DEFINER` function `tenant.tenant_provision(...)`
  (same trust boundary and grant pattern as `tenant.tenant_list_all()`,
  migration `fdd3afde337c`): a narrow, single-purpose INSERT that bypasses RLS
  for exactly one row. `TenantRepository` gains `add(tenant)` calling it.
  Unique violations map to `ConflictError`.
- **Application.** `ProvisionTenantUseCase` sequences: pre-check admin email
  (`auth_find_user_by_email`) → create tenant (own UoW, committed) → invite the
  admin. `InviteStaffUserUseCase` is **reused, not copied**: its body moves into
  `invite()` returning `(user, raw_token)`; `execute()` keeps its signature.
  The staff/token repositories open their own sessions, so the tenant must be
  committed first; on the rare invite failure the tenant is closed
  (compensation) and the error re-raised.
- **API.** `routers/platform.py` `POST /agencies`; OpenAPI re-exported and the
  Angular client regenerated.
- **Audit.** Automatic — `SqlAlchemyUnitOfWork`'s `AuditRecorder` captures the
  tenant insert and user rows.
- **Frontend.** Agency Management page gains a "Create agency" dialog
  (`lpg-form-field`, stacked labels) and a success dialog showing the one-time
  setup link with a copy button (clipboard API needs a secure context, so the
  link is also shown in a selectable read-only field) and a "Next: issue a
  license" link.

## Risks

- Cross-session sequencing (tenant commits before the admin exists) — mitigated
  by the pre-check and compensating close; covered by an integration test that
  forces the invite to fail.
- Slug is a future subdomain: choosing the stricter DNS-safe format now avoids
  a later data migration.
- Returning a credential-equivalent token in an API response: HTTPS is required
  in production (currently HTTP-only until a domain exists — recorded in
  `infrastructure/deploy/DEPLOY.md`); token TTL reuses
  `password_reset_token_ttl_seconds`, single-use via the existing reset flow.


> **Update 2026-09-26 (Phase 31):** the 1-hour setup-link lifetime described above proved
> unworkable and left agencies with no recovery path. Links a Super Admin issues now last 24 hours
> (`setup_link_ttl_seconds`), and the Platform Console can list an agency's users, add an admin
> and issue a fresh link - see ADR-049 and `planning/features/31-agency-user-management/`.
