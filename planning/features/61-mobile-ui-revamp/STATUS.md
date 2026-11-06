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

### Fix: provider state survived sign-out (shared-phone data leak) (done, verified by tests)
Found while building R1 (see PR notes): providers lived in one `ProviderScope` for the whole run, so after a sign-out the next person to sign in on the same phone could see the previous person's cached screens (for example the Admin dashboard numbers) until each refreshed.
- **Fix:** `SessionScope` (in `auth`) gives each app a new state tree, via a new key on its `ProviderScope`, whenever a *signed-in* session ends (log out or an expired session). It does not fire when the app starts and finds no session, or on sign-in. All three apps use it in `main.dart`.
- **Tests:** `auth` (key changes only on signed-in to signed-out; discarded state is rebuilt; start-up with no session does not rebuild; repeated sign-outs) and an Admin test with the real dashboard provider: person A's numbers are gone for person B, plus a control test showing A's numbers *do* survive without the scope, which reproduces the bug.
- **Cost:** the screen state is rebuilt on sign-out, which is the point (the app goes to the sign-in screen anyway).
- **Still open (not fixed here):** in the Driver app, a *forced* sign-out (expired session) does not clear the on-device read cache, and neither sign-out path removes the unsent offline queue. A different driver signing in on the same phone could see the previous driver's cached route when offline, and the previous driver's unsent deliveries would be sent under the new session. Clearing the queue on a forced sign-out would lose unsent deliveries, so this needs a decision (keep per-driver queues, or block sign-in until the queue is sent). Added to TASKS.md.

### Fix: offline queue and cache leaked between drivers on a shared phone (done, verified by tests; stacked on the SessionScope fix)
- **Cause:** the offline queue (`sync_operations`) and read cache (`cached_resources`) had no owner. After a forced sign-out the next driver could be shown the previous driver's cached route while offline, and the previous driver's unsent deliveries would have been sent under the next driver's session. (The Customer app shares the same queue.)
- **Chosen design (the plan's open question):** per-user ownership, not wiping. Every queued operation is stamped with the user who queued it and is **sent, counted and listed only under that user's session**; it stays in the queue, **not lost**, and resumes when its owner signs in again. With nobody signed in, nothing is sent. Cache rows carry the owner in their key, so another user never reads them. Wiping on a forced sign-out was rejected because it would silently lose unsent deliveries.
- **Changes:** database schema v5 (`owner_id` on both tables; the cache is rebuilt, the queue is kept); `ResourceCache(owner:)`; `SyncCoordinator(currentOwner:)` is now required, so no caller can forget it; Driver and Customer wire it to the signed-in user; the Driver's cache provider is owner-scoped.
- **Upgrade rule:** operations queued before owners existed have no owner; the first user to sign in after the upgrade adopts them (on a phone with one driver that is their owner; leaving them unowned would strand unsent deliveries). On a phone already shared by two drivers with unsent work, that adoption could assign it to the wrong person; accepted as a one-time edge case.
- **Tests:** `sync_engine` (stamping, never sent under another session and not lost, resumes for its owner, nothing sent when signed out, counts and lists scoped, adoption), `local_storage` (cache scoping, eviction, explicit-logout clear, and a real v4 to v5 migration that keeps queued operations), and a Driver scenario test (driver 2 offline gets nothing of driver 1's).
- **Not covered:** photos and signatures on disk for a queued delivery stay until the delivery is sent (the database is encrypted, those files are not); an explicit log out still clears the whole read cache but leaves the queue, which is intended.
- **Depends on** the `SessionScope` PR: the live counters take their owner when created, and `SessionScope` rebuilds them on sign-out.

### Fix: proof-of-delivery photos and signatures were plain files on disk (done, verified by tests; stacked on the queue-ownership fix)
- **Cause:** the queue database is encrypted, but the photo and signature of an unsent delivery were written as plain files under the app's support folder, and a file was only deleted after a *successful* send. A discarded or conflicted delivery left its files behind for good.
- **Encrypted at rest:** `EncryptedMediaStore` (AES-256-GCM, fresh nonce per file, `cryptography` 2.9.0, pure Dart) wraps the file store; the key is a random 256-bit secret in secure storage (Keychain or Keystore), created on first use. A tampered file or a wrong key fails to read instead of returning garbage. A plain file written before the upgrade still reads (so an unsent delivery is not stranded) and is deleted as usual once sent.
- **No orphans:** discarding a delivery (the driver acknowledging a conflict or giving up on a failed one) deletes its photo and signature; at start-up `purgeOrphanedMedia` removes stored files no queued operation refers to, keeping anything written in the last hour (a delivery writes its media just before it is queued). A *failed* delivery keeps its files, because the driver can still retry it.
- **Tests:** round trip; the file on disk contains none of the photo and differs per write; wrong key and tampered file rejected; legacy plain file still reads; the key is loaded once; discard deletes media; orphan purge removes old unreferenced files and keeps queued, recent ones.
- **Limits:** this protects files at rest on the phone; it does not hide them from the app itself while it runs. Old sent rows are now pruned (next section).

#### Pruning old sent operations
- **Why:** a sent operation is never retried (its idempotency key is on the server) and nothing in the apps reads it, but its payload still holds customer details and it stayed on the phone for ever.
- **What:** `SyncCoordinator.pruneSyncedOperations` deletes `synced` rows whose send time (or creation time, for a row with no attempt recorded) is more than **7 days** old. The week is a decision of mine (a short window for finding out what a driver sent); change `olderThan` to taste. It runs at start-up and at most every **6 hours** after a sync pass, before the orphaned-media sweep, and never blocks or breaks sending (errors are swallowed and it retries next time).
- **Never touched:** `pending`, `error`, `syncing`, `failed` and `conflict` rows, however old; they are unsent work or need the driver's attention. A just-sent row is kept for the week.
- **Checked first:** only the coordinator writes `synced`, and no screen or provider reads those rows (the live lists filter on the other statuses).
- **Tests:** old sent rows deleted and recent ones kept; every unsent status kept at 30 days old; the creation-time fallback; adjustable retention; a normal sync pass and `start()` both tidy up without touching what was just sent.
- **Old failed rows (added at the owner's request):** `pruneFailedOperations` deletes `failed` rows (retries used up, or a permanent refusal) untouched for more than **30 days**, **together with their photo and signature**. Same schedule as the sent-row pruning. **This permanently discards a delivery that never reached the server**, which is why the window is 30 days, not 7, and why it is a decision to confirm: until then the driver can retry or discard it from the sync screen. Failed rows judged by last attempt (creation time if none). `conflict` rows (a stale change the server already moved past), and all `pending`, `error` and `syncing` rows, are never pruned. A deleted failed delivery leaves no trace on the phone, and there is no log; if the office needs to know about such losses, that needs a server-side record, not done here.
- **Tests (failed rows):** 30-day-old deleted and newer kept; conflicts and every waiting or retrying row kept at 90 days old; creation-time fallback; adjustable retention; its photo and signature deleted with it while a newer one's are kept; start-up prunes them.
- **Old conflict rows (added at the owner's request):** `pruneConflictedOperations` deletes `conflict` rows (the server answered `409`: someone else, usually the office, had already moved that order on) untouched for more than **30 days**, with their photo and signature. A conflict is the lowest-risk of the three because the server is authoritative: what is thrown away is a change it already decided against, and the driver only ever had to acknowledge it. 30 days is the same window as failed rows; it is its own parameter if you want it shorter. A driver who never opened the sync screen in a month loses the note that their change was rejected. Waiting, retrying and failed rows are untouched.
- **Tests (conflict rows):** 30-day-old deleted and newer kept; failed and every waiting or retrying row kept at 90 days old; creation-time fallback; adjustable retention; photo and signature deleted with it; a real `409` becomes a conflict that a later prune removes; start-up prunes them. The shared delete logic also backs the failed-row prune (its tests still pass).
- **Old cache rows (added at the owner's request):** `ResourceCache.pruneStale` deletes cached rows, **whoever owns them**, not written for more than **14 days**. It is the lowest-risk prune: the cache only holds copies of what the server has, a row is rewritten on every successful refresh (so active data stays fresh), and data nobody fetched for two weeks is stale anyway. It removes, for example, the route of a driver who no longer uses the phone. The Driver app runs it, best-effort and off the critical path, when its cache is first built (app start, and again after a sign-out rebuilds the app state); the Customer app has no read cache. An explicit log out still clears the whole cache. The 14 days is my choice; it is a parameter. Trade-off: a driver who is offline for over two weeks on the same row would lose that offline fallback, which is unrealistic for a delivery round.
- **Tests (cache rows):** `local_storage`: old rows of any owner deleted and recent kept; a row refreshed just now survives even if it started old; adjustable; empty cache. `driver_app`: on a real encrypted database the provider prunes a 40-day-old row and keeps a 2-day-old one (checked that the test fails when the prune call is removed).
- **Cache rows of drivers who have signed out (added at the owner's request):** `ResourceCache.pruneOtherOwners` deletes the rows of **everyone but the signed-in user** not written for more than **2 days**: the cache of a driver who signed out of this phone. It is quicker than the 14-day sweep because nobody here should hold another person's data for long; the 2 days is my choice (it lets a driver who signs back in after a shift change still find their route cached; anything older is refilled by their next online fetch). It **does nothing while nobody is signed in** (the cache's owner is unknown), so a driver whose session is still being restored is never mistaken for a stranger, and the signed-in user's own rows are never touched by it, however old. The Driver app runs it whenever the session becomes signed in (a restore at start-up or a later sign-in), and again if the cache is rebuilt. Rows written with no one signed in count as someone else's.
- **Tests (signed-out drivers' rows):** `local_storage`: other users' rows older than 2 days deleted while own rows survive; other users' recent rows kept; nothing happens with no signed-in user; rows of no owner count as someone else's; adjustable grace. `driver_app` on a real encrypted database: pruning when signed in at build; a returning driver's rows kept while nobody is signed in; pruning on a **later** sign-in (checked: the test fails if the sign-in trigger is removed). The provider's own "signed in" guard is redundant with the cache-level one, so removing it alone does not fail a test; the cache-level guard is what protects the returning driver.
- **Flaky test found and fixed:** the "a real 409 ends up as a conflict that a later prune removes" test I added with the conflict prune compared against a cutoff of *now*, but times are stored to the whole second, so it passed only when a second boundary happened to pass (it failed 5 of 6 runs when I re-ran it). It now moves the cutoff clearly into the future; 6 of 6 runs pass. The earlier "all passed" for that commit was a lucky run.
- **Not covered:** nothing on the phone from the queue or cache is now kept without an age limit, except `conflict` and `failed` rows younger than 30 days and unsent work, by design.

#### Speed of the encryption (measured, then fixed)
First measurement of pure-Dart AES-GCM on this server (Xeon 2.1 GHz, JIT and AOT alike): about 6 to 8 MB/s, so a 3 MB photo took about 0.45 to 0.58 s to encrypt and 0.38 s to decrypt, **all on the main isolate, freezing the screen**. Fix: the cipher is now pluggable (`MediaCipher`).
- **Background isolate (default everywhere):** same pure-Dart AES-GCM off the UI thread. Measured (AOT, encrypt plus decrypt): 3 MB 851 ms inline, freezing the calling isolate for **855 ms**, versus 908 ms on a background isolate with a freeze of **9 ms (worst 76 ms)**; 8 MB 2239 ms inline, freeze **2243 ms**, versus 2207 ms with a freeze of **15 ms**. It is about 7 percent slower overall but never freezes the app. A test asserts the event loop keeps turning during a 3 MB encryption.
- **Native AES on Android and iOS (Driver app):** `cryptography_flutter` uses the phone's own AES for payloads from 2 KB to 20 MB on Android. The Driver app tries it first and falls back to the isolate cipher if it is unavailable or fails (then stops trying it). `--dart-define=NATIVE_MEDIA_CIPHER=false` forces the isolate cipher, to compare the two on a real phone. All implementations seal the same layout, so a file written by one opens with another (tested); a tampered file is rejected and not retried.
- **Not measured:** the native path itself (it needs a real Android or iOS device), and anything on a real budget phone. The package source marks Android AES-GCM with a TODO calling its implementation slow, even though it enables it, so **the native speed on Android must be checked on a device** before trusting it; the isolate fallback and the kill switch exist for that reason. Android needs the plugin's minSdk 24 (the app takes the larger of Flutter's default and 23, so confirm Flutter's default is 24 or raise it); iOS is 13+, which the app already targets. No Android or iOS build was run here.

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
