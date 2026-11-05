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


### Done in A2 (backend enforcement)
- Sessions are bound to the phone at sign-in, OTP verify and refresh (`did`/`app` token claims; `identity.refresh_token.device_id`, migration `d7a3b5e9c218`). Sign-in, OTP-verify and refresh bodies take an optional `device` object; the install ID travels in `X-Device-Id`, the app kind in `X-App-Type`.
- Every authenticated request is checked in `get_tenant_context` against a Redis-cached status; `GET /api/v1/devices/me` is the one call a waiting or blocked phone can still make. The realtime connection is checked at connect, on token refresh and every quiet 30 seconds.
- Block/remove revoke that phone's refresh tokens, clear the cache, publish `device.status_changed` over realtime and push `device_blocked_user` to the signed-in user. A refresh token opened on one phone cannot be redeemed from another under `enforce`.
- Changing `device_control` through `POST /admin/tenant-configuration` clears the cached mode at once.
- Error codes: `DEVICE_REQUIRED` (401), `DEVICE_PENDING`, `DEVICE_BLOCKED`, `DEVICE_REMOVED` (403).

### Decisions taken in A2
- **A waiting phone can sign in** (so it has a session to ask "am I approved yet?") but every request except `GET /devices/me` is refused.
- **A driver login is the Driver app even without headers**; under `enforce` a driver session with no phone gets 401 `DEVICE_REQUIRED`, which the app answers by refreshing with its device headers (that binds it).
- **Admin app staff are recognised by `X-App-Type: admin_app`** at sign-in. A staff password used with no app headers is a dashboard-style session and is not device-controlled. This is a real limit of the design (a credential is not a phone) and is recorded in ADR-071 for the security review.
- **Block is event-driven**: the decision commits first, then a handler clears the cache and revokes tokens. Handlers log failures instead of failing the admin's request, because request checks read the database truth within 30 s anyway.


### Done in B (dashboard)
- Settings > Linked Devices is a real page: the `device_control` switch (Off, Watch only, Approve phones), state tabs with the waiting count, an app filter, a table (phone, model, software, app and version, signed in as, state, first and last seen), and a drawer per phone with actions, rename, IMEI/serial note and change history.
- Pending badge on the sidebar Settings item and next to Linked Devices in the Settings nav; it refreshes from a live `device_pending_staff` message and every 2 minutes, for users holding `license:manage_tenant` only.
- A `device` notification opens the Linked Devices page.
- Generated API client regenerated; only device-related changes kept. The committed client was already behind the committed OpenAPI spec for an unrelated order-settlement endpoint; that drift is **not** included here.

### Decisions taken in B
- Words for the admin are plain: "Waiting" (not pending), "Watch only", "Approve phones".
- Switching to "Approve phones" asks first and says how many phones are still waiting.
- The generic Configuration page is untouched; the mode lives on this page only.
