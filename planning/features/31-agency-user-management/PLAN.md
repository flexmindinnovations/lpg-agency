# Plan: Agency User Management (Super Admin recovery + extra admins)

**Phase:** 31
**Status:** Planned 2026-09-26.

## Problem

`POST /platform/agencies` (Phase 30) creates an agency and its first admin, and
returns a one-time setup link. Nothing else in the Platform Console touches an
agency's users. Consequences found in production on 2026-09-26:

- The setup link is single-use and expires after **1 hour**
  (`password_reset_token_ttl_seconds`). Miss the hour, lose the link, or forget
  the password, and the agency is **locked out with no recovery path**:
  "forgot password" only writes the email to the server log
  (`LoggingEmailSender`), and there is no change-password endpoint.
- A Super Admin cannot add a second admin to an agency.

## Scope

Three Platform Console routes, all `tenant:manage_platform`, live-checked:

| Route | Purpose |
|---|---|
| `GET  /platform/agencies/{tenant_id}/users` | List the agency's staff users (email, role, active). Metadata only. |
| `POST /platform/agencies/{tenant_id}/admins` | Add another `agency_admin`; returns a one-time setup link. |
| `POST /platform/agencies/{tenant_id}/users/{user_id}/setup-link` | Issue a fresh setup link for an existing **`agency_admin`** (lost/expired link, forgotten password). Invalidates the user's older unused links. |

Plus a Users section in the agency detail drawer (list, "Add admin", "New setup
link") reusing the one-time-link drawer.

## Decisions

- **Setup links last 24 hours** (new setting `setup_link_ttl_seconds`, default
  86 400), still single-use. Applied to every link a Super Admin issues, including
  Create agency (previously 1 h). Ordinary forgot-password links stay at 1 h.
  The tenant-side `/admin/users` invite is unchanged.
- **Recovery is limited to `agency_admin` users.** Other staff are recovered by
  their agency's admins, which keeps a Super Admin's reach to the smallest set
  that still un-sticks an agency.
- **Every use is audited**, attributed to the *target agency* (so the agency's own
  admins can see "platform staff issued a setup link for X" in their audit log),
  actor = the Super Admin. The audit hook cannot see these writes (the staff and
  token repositories open their own sessions), so the use cases write an explicit
  audit entry through a small port. Never contains the token.
- **Trust tradeoff (recorded, accepted):** the Platform Console was designed to
  keep the Super Admin out of agency business data. Minting an admin or a reset
  link is an indirect way in. It is the only recovery path while there is no
  email provider, so it is kept, audited and visible to the agency.
- Guards: agency must exist and not be `closed`; admin email is globally unique;
  a setup link needs an **active** `agency_admin` belonging to that agency (RLS
  makes another agency's user invisible -> 404).

## Design

- **Application** (`application/platform/agency_users.py`): `ListAgencyUsers`,
  `AddAgencyAdmin` (reuses `InviteStaffUserUseCase.invite()`), `IssueSetupLink`
  (new token, invalidates older unused ones). `PlatformAuditTrail` port.
- **Persistence:** migration adding `identity.auth_invalidate_password_reset_tokens`
  (`SECURITY DEFINER`, same pattern as the other `auth_*` token functions - the
  token table is RLS-protected); `PasswordResetTokenRepository
  .invalidate_unused_for_user()`; `SqlAlchemyPlatformAuditTrail`.
- **API:** three routes in `routers/platform.py`, each opening the platform UoW
  scoped to the target agency; schemas in `schemas/admin.py`.
- **Frontend:** `AgencyService` methods, generated client, Users section, generic
  setup-link drawer (Create agency now uses it too).

## Risks

- Reset-link use does not revoke a user's existing refresh tokens
  (`ConfirmPasswordResetUseCase` predates this). A recovered account keeps its old
  sessions until they expire - recorded as a known gap, not fixed here.
- The raw setup link is returned in an API response (and `LoggingEmailSender`
  still logs it) - the accepted state until an email provider exists (ADR-048).
