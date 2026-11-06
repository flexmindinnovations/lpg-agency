# Status: Mobile UI/UX Revamp, i18n, Device Control and Alert Sounds

**Plan approved by the owner; Epic 11 (device registration and access control) is being built first, in stacked PRs. Everything else is not started.** (Plan version 5, 2026-11-05.)

## Done so far
- `lpg-domain-expert` agent created (`.claude/agents/lpg-domain-expert.md`) for wording, flow and domain-visual reviews.
- Existing in-progress UI work saved on branch `wip/mobile-ui-refresh` (unverified).
- Current state surveyed (PLAN.md section 2), including why Linked Devices is empty: no code registers a device, revoking has no effect, and there is no `admin_app` type.
- Owner's inputs recorded: no transparent glass, i18n with JSON catalogues, device control for Driver and Admin, louder custom alert sounds (Driver first).
- Sequencing decided: alert sounds (Epic 12) are built last, after the UI, i18n and device-control work; alerts keep the default sound until then.
- Sound sourcing decided: open source, CC0 first, domain-themed, used only in the three apps' notifications. Candidate sources and licences checked on 2026-11-05 (Freesound CC0 filter, Kenney, akx/Notifications); nothing downloaded yet.
- Notification pipeline surveyed: FCM messages carry no channel, sound or priority; all apps share one default-sound channel.
- The Admin dashboard "error then data" cause is **not yet confirmed**; story 0.4 reproduces and fixes it.

## Not done
Everything in TASKS.md.


## Epic 11: device registration and access control (in progress)
Built in stacked PRs, each opened against `docs/mobile-ui-revamp-plan`: **A1** backend device registry (this PR), **A2** backend enforcement, **B** dashboard, **C** mobile, **D** tests and security review. Optional stories 11.9 (pairing code) and 11.11 (Play Integrity / App Attest) are skipped.

### Done in A1
- `admin_app` app type; `LinkedDevice` has the four states, phone details, last user, asset note; `platform.linked_device` extended by migration `c4e8a1f7d305` (already RLS-scoped; status check constraint; backfill: revoked rows become `removed`, others `approved`).
- Use cases: register-at-sign-in (no caller yet), approve, block, unblock, remove, rename/IMEI note, list with filters, pending count, history. Approve and unblock are refused over the plan's seat limit.
- API under `/api/v1/admin/license/devices` (agency admin, `license:manage_tenant`; managers get 403). The old `PATCH …/revoke` is gone.
- Named audit entries for register, approve, block, unblock, remove, update; `last_seen_at`-only changes are not audited.
- `device_control` tenant setting (`off`/`observe`/`enforce`), validated on write.
- Admin alert `device_pending_staff` (normal tier, push + in-app) for agency admins.
- ADR-071.

### Decisions taken (owner's decisions are not reopened; these fill the gaps)
- **`device_control` replaces the grace period.** Default `off`: nothing enforced, nothing recorded, so existing agencies and phones are unaffected at deploy. `observe`: phones register themselves (approved while seats remain, pending once the plan is full), nobody blocked. `enforce`: pending/blocked/removed phones are refused. Unknown value reads as `off`.
- **Identifiers are stored hashed** (install ID, Android ID / vendor ID). The dashboard shows an 8-character reference. Reason: a database leak must not yield usable device keys, and it keeps the personal-data footprint small.
- **Only approved phones hold a seat.** Pending phones do not count; blocking and removing free the seat.
- **A removed phone that signs in again becomes pending**, never straight back to approved.
- **A driver login is always the Driver app**; staff on the web dashboard carry no device and are not controlled. The Admin app is recognised by the `X-App-Type` header it sends.
- **Audit:** explicit named entries plus the generic row-diff entry. The IMEI/serial note text is never put in an explicit entry.
- **Status codes:** `DEVICE_REQUIRED` 401 (so the app's silent refresh re-binds), `DEVICE_PENDING`/`DEVICE_BLOCKED`/`DEVICE_REMOVED` 403.
- **Notification tier:** the repository has no sound tiers yet (Epic 12 is last), so the new alert is a normal push + in-app notification.

### Verified in A1 (run in this cloud session)
`ruff check`, `ruff format --check`, `mypy` (strict), `lint-imports`, `pytest tests/unit`, and the new integration tests against a real PostgreSQL 16 and Redis started locally (no Docker here). `export_openapi.py --check` passes after regenerating the spec. See the PR for the full-suite result.

### Not verified / open
- Real-phone check of what can be read (11.1) is still open.
- Legal wording on privacy is unverified (ADR-071).
