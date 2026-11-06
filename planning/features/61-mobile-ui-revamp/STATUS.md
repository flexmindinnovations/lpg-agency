# Status: Mobile UI/UX Revamp, i18n, Device Control and Alert Sounds

**Plan approved by the owner. Epic 11 (device registration and access control) was built first, in stacked PRs now merged into the plan branch (see the Epic 11 section below). Release R1 (epics E0 to E3) follows, one story per PR stacked on the plan branch `docs/mobile-ui-revamp-plan` (PR #122), and is in progress.** (Plan version 5, 2026-11-05.) Tick state is in [TASKS.md](./TASKS.md).

## How things were verified in this stage
Flutter 3.47.9 (Dart 3.13.7, stable) was installed in the cloud environment, so `dart format --set-exit-if-changed .`, `flutter analyze` and `flutter test` were **actually run** for every package and app a PR touches (the commands CI runs, `.github/workflows/mobile-ci.yml`). Nothing could be run on a device or emulator: **UI behaviour is verified by widget and provider tests only**, never by looking at a running app.

**Known flaky tests (pre-existing, not caused by this work).** In `driver_app`, `test/offline/delivery_mutations_test.dart` ("departStop moves the cached order optimistically...") and `test/features/delivery/location_sharing_test.dart` ("reports a fix while the route is in progress") fail intermittently in full-suite runs and pass alone. Confirmed on an unchanged checkout of the plan branch (one pass, one fail in two full runs). The final full `driver_app` run for story 0.4 passed (112 tests) on the third attempt. They are timing-dependent and worth a separate fix.

## Done so far
- `lpg-domain-expert` agent created (`.claude/agents/lpg-domain-expert.md`) for wording, flow and domain-visual reviews.
- Existing in-progress UI work saved on branch `wip/mobile-ui-refresh` (unverified); reference only.
- Current state surveyed (PLAN.md section 2), including why Linked Devices is empty.
- Owner's inputs recorded: no transparent glass, i18n with JSON catalogues, device control for Driver and Admin, louder custom alert sounds (Driver first); alert sounds sequenced last.

### Story 0.4: dashboard "error, then data" (done, verified by tests)
**What the code showed.**
- Admin turned Riverpod's retry **off** (`retry: (_, _) => null`), so the first failed request showed the error screen at once. The shell's realtime `reconnected` refetch then produced the data: exactly "error, then data".
- Customer and Driver did the opposite: they kept Riverpod's **default** retry, which retries *every* failure (including a 403 or 404) up to ten times with growing delays, so a real error hid behind a skeleton for about half a minute.
- On a refresh, a quiet retry (or a failed refresh) swapped the old numbers for a skeleton or an error, because Riverpod's `when` flags cannot express "keep old data, but show the skeleton during a first-load retry".

**What is NOT confirmed.** *Why the first request fails on the owner's device.* It could not be reproduced here (no device, no backend). The 401 refresh path was checked by reading the code and is not the cause at start-up: the router only builds the dashboard once the session is authenticated, token refresh is single-flight, and the first request carries a fresh token. The remaining candidates are a transient network or server failure at start (radio not up yet, or a gateway answering 502/503/504 while the server wakes), which is what the sequence tests simulate. The fix is a policy that absorbs any such transient failure; if the error still appears on a device after this, the cause is something else and the next step is request logging on that device.

**Fix (all three apps).**
- `api_client`: `quietRetry` (one retry, after `quietRetryDelay` of 2 s, only for transient failures: no network, 502/503/504, or an unstructured response; a structured answer such as `FORBIDDEN` or `NOT_FOUND` is shown at once) and `isTransientError`. `mapDioError` now maps 502/503/504 to `SERVER_UNAVAILABLE`. `FailureCarrier` and `FailureException` carry the error code through providers; the Customer and Driver providers now throw `FailureException(failure)` instead of `Exception(failure.message)` (same printed message, plus the code).
- `design_system`: `AsyncValue.whenQuiet` (value present: show it; no value and loading or retrying: skeleton; neither: error). It adds a dependency on the pure-Dart `riverpod` package and is the seed of `LpgAsyncView` (story 3.1).
- Each app's `ProviderScope(retry: quietRetry)`. Admin dashboard (both sections), Customer home (balance and recent orders) and Driver Today use `whenQuiet`.
- The other ~125 hand-written `.when(...)` sites keep their current behaviour: the first-load rule (skeleton during the quiet retry, error after) now holds everywhere through the app-wide retry; "keep old data on refresh" holds only on the screens converted above and is rolled out with story 3.1 onwards.

**Tests added** (all pass): `api_client/test/quiet_retry_test.dart`; `design_system/test/quiet_when_test.dart` (the exact provider states, including a retrying first load); `admin_app/test/dashboard_first_load_test.dart` (a reproduction with retries off showing the error, then data; plus quiet retry, bad gateway, error after two failures, no retry of a refusal, old data kept through a failed refresh); `customer_app/test/features/dashboard/dashboard_first_load_test.dart`; `driver_app/test/features/delivery/today_first_load_test.dart`.

**Decision recorded (plan's recommended option):** the quiet retry waits 2 seconds, once. Not yet chosen by the owner; change `quietRetryDelay` if it feels long.

### Story 0.1: design direction (done)
[design-direction.md](./design-direction.md): the modern solid enterprise look as rules (tonal elevation, soft shadows, 1 px hairlines, 16 to 20 px radii, type scale, purposeful motion, high contrast, WCAG 2.2 AA), grounded in what the code already has, with one reference screen per app. It is a documentation story: nothing was built or run. Constraint recorded for story 1.1: `tokens.json` is shared with the Angular dashboard. Decision recorded (plan's recommended option): per-app accent proposed as Admin blue, Customer and Driver flame orange; the owner may change it.

## Not done
Everything else in TASKS.md (epics E2 from 2.2, E4 to E10 and E12).



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

### Done in C (mobile)
- New package `mobile/packages/device_identity` (added to `mobile-ci.yml`): random install ID in secure storage; phone details (maker, model, OS, app version, platform, Android ID / iOS vendor ID); `DeviceInterceptor` adds `X-Device-Id` / `X-App-Type` to every request and the `device` object to the sign-in, OTP-verify and refresh bodies, and reports `DEVICE_*` refusals; `DeviceApi` (`GET /devices/me`); `DeviceAccessController` (allowed / pending / blocked); `DeviceControl` (router redirect, follows the session and app resume); three screens (name this phone, waiting, blocked).
- Driver and Admin apps: `main.dart` calls `DeviceControl.setUp` right after creating the `ApiClient` and before the session restore (the restore is the first request and must carry the install ID); routers merge the device state into `refreshListenable` and call `deviceControl.redirect` first. Wording lives in one file per app (`lib/src/device_strings.dart`).
- `RealtimeClient`: optional `getInstallId` (sent as `device_id` in the auth frame) and `subscribeToDeviceChanges()`. A `device.status_changed` message makes the app ask the server where it stands.
- `SyncCoordinator`: a `DEVICE_*` refusal puts the operation back as `pending`, stops the pass, calls `onDeviceRefused`; nothing is failed, counted or discarded. The Driver app resumes with `syncNow` when the phone is allowed again.
- Wording was reviewed by the `lpg-domain-expert` agent and adopted (no menu path for drivers, an explicit "do not delete the app or clear its data" warning, a full list of what is sent, no security promise).

### Decisions taken in C
- **Name step:** the user names the phone once, before the first sign-in (default: the model). A session that began before this version silently takes the model as its name instead of being interrupted.
- **Blocked:** the app signs the user out and shows the blocked screen; "Try signing in again" leaves it, and the server refuses again if the phone is still blocked. Local data is never wiped.
- **Waiting state is forgotten** when the user signs out of a waiting phone.
- **`android_id` ^0.5.2** rather than 0.6.0, so the apps' minimum Flutter version does not rise (0.6.0 needs 3.47).
- **Push:** a blocked user gets a visible `device_blocked_user` push (from A2). The app does not act on the push itself; it asks the server when it next comes to the foreground, or at once if the live connection is open.

### Not verified in C
- Nothing was run on a device or emulator (none available). Screens, the Android ID plugin, secure storage and the real realtime close behaviour are verified by Flutter tests and analysis only.
- Whether Google Play's rules and India's DPDP Act need a disclosure for the Android ID is unverified (the privacy line is plain wording, not legal advice).
- Open questions for a real agency (from the wording review): who should a driver call, should the screen show a call button with a number the agency sets, and can an office user ever approve their own phone.

### Done in D (tests and security review)
- Enforcement matrix and hardening tests (see the review). Two real findings fixed: a chatty realtime client escaped the periodic device re-check, and one login could flood the approval queue (now capped at 5 waiting phones, `DEVICE_QUEUE_FULL`).
- Security review written up at `docs/reviews/2026-11-05-device-control-security-review.md`. It is a self-review with adversarial tests, not an independent review or a penetration test. Main residual risk: device control stops a phone, not a credential (the web dashboard and header-less staff sessions are not controlled).
- Epic 11 is code-complete except the real-phone check in 11.1 and the optional 11.9 / 11.11, which were skipped as agreed.
