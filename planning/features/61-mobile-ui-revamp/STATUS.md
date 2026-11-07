# Status: Mobile UI/UX Revamp, i18n, Device Control and Alert Sounds

**Plan approved by the owner. Epic 11 (device registration and access control) was built first, in stacked PRs now merged into the plan branch (see the Epic 11 section below). Release R1 (epics E0 to E3) follows, one story per PR stacked on the plan branch `docs/mobile-ui-revamp-plan` (PR #122), and is in progress.** (Plan version 5, 2026-11-05.) Tick state is in [TASKS.md](./TASKS.md).

## How things were verified in this stage
Flutter 3.47.9 (Dart 3.13.7, stable) was installed in the cloud environment, so `dart format --set-exit-if-changed .`, `flutter analyze` and `flutter test` were **actually run** for every package and app a PR touches (the commands CI runs, `.github/workflows/mobile-ci.yml`). Nothing could be run on a device or emulator: **UI behaviour is verified by widget and provider tests only**, never by looking at a running app.

**Known flaky tests (pre-existing, not caused by this work).** In `driver_app`, `test/offline/delivery_mutations_test.dart` ("departStop moves the cached order optimistically...") and `test/features/delivery/location_sharing_test.dart` ("reports a fix while the route is in progress") fail intermittently in full-suite runs and pass alone. Confirmed on an unchanged checkout of the plan branch (one pass, one fail in two full runs). The final full `driver_app` run for story 0.4 passed (112 tests) on the third attempt. They are timing-dependent and worth a separate fix.

## What is visible on a phone today (checked on the emulator, 2026-11-06)
Flutter 3.47.9, Pixel 10 Pro emulator, debug builds against the local backend. All three apps build, and `flutter analyze` and `flutter test` pass in every package and app.

**The screens still look like the old design.** What has merged is the foundation only: the design direction note, the token audit, the theme engine, solid surfaces (E1), the i18n plumbing (2.1), `LpgAsyncView` (E3), and device control (E11). Together they change very little on screen (slightly different surfaces and snackbars, no translucent fills, a quiet retry at start-up). `LpgAsyncView` is used on three screens only: the Admin, Customer and Driver dashboards (Driver: Today). No existing string has been moved into a catalogue (2.4 to 2.8). Not started, so not visible: the new component library (E4), domain icons and illustrations (E5), tablet and adaptive layouts (E6), and the screen-by-screen rollouts for Customer, Driver and Admin (E7 to E9). The visible redesign starts with E4 and E7 to E9.

**Found on the emulator and fixed in the change that adds this section:** the Admin hero card's stats line ran into its watermark icon (new `keepClearOfWatermark` option); the sign-in "OTP has expired" message also appeared for a code that had already been used (now "This code is no longer valid. Please request a new code."); the main Android manifests allowed plain-HTTP traffic in release builds (removed; the debug manifests keep it for local testing against `http://10.0.2.2:8000`).

**Device control, checked on the emulator against the local backend:** a fresh sign-in under `enforce` registers the phone as waiting; approving it lets the driver in; blocking it signs the running app out within seconds. Story 11.1 (what a real phone can report) is still open.

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

### Story 0.2: i18n tooling spike (done, verified by tests)
Decision and comparison: [i18n-decision.md](./i18n-decision.md). Recommended **slang** (typed JSON, `locale_handling: false`, one `LocalizationsDelegate` per catalogue) over `gen-l10n`; the choice was close and is cheap to reverse. Working example in `design_system` with a second test locale (`hi`) proves: JSON per locale, typed keys (a wrong key is an analyzer error), typed placeholders, plurals, English fallback, runtime switch through `MaterialApp.locale` (also switching Flutter's built-in widget text via `flutter_localizations`), and Indian number and date formats through `intl`. Package versions were read from pub.dev (slang 4.19.2, slang_flutter 4.19.0).
- **Gap found:** a key that exists only in a translation is silently dropped by the generator; story 2.1 adds a CI check.
- **Open product decision (not blocking):** digits for Marathi (native by default in `intl`) versus Latin everywhere for money; recommended Latin. See the decision note.
- **The Hindi strings are test data**, not reviewed translations; they must be replaced before Hindi is offered.
- Pre-existing and unchanged: the next free ADR number is 071 on `main`; none was allocated.

### Stories 1.1 to 1.3: token audit, theme engine, surfaces (done, verified by tests)
Details: [token-audit.md](./token-audit.md).
- **1.1 Token audit.** One map of where each token kind lives; no colour literals and no blur existed. Twelve translucent fills made solid (`LpgColors.tint`, `heroMuted/heroSubtle/heroTrack`). A test scans the design system and the three apps and fails on blur or alpha-blended fills outside a short allow-list. Found and fixed muted hero text under AA (3.97:1 to above 4.5:1).
- **1.2 `LpgThemeEngine`.** One engine per app (`accent`, text-scale limit, `reduceMotion`), with light, dark and high-contrast themes from the single token source, `LpgDensity` by size class (`LpgSizeClass`), a text-scale clamp, and reduce motion (platform or forced; page transitions go instant). The three apps use it and build no `ThemeData`.
- **1.3 Surfaces.** Four solid layers (canvas, card, sheet, inverse), `LpgSurface`, hairlines and shadows from one place; dialogs, sheets and menus use the sheet layer, snackbars the inverse layer. `tokens.json` was not touched, so the web build is unaffected.
- **Behaviour changes (deliberate, all small):** Admin now passes the high-contrast theme in dark mode too; dark-mode snackbars are light (inverse layer) instead of card-coloured; text scale is capped at 2.0x; page transitions are instant under reduce motion; solid tints replace translucent ones.
- **Decision recorded:** the per-app accent stays flame orange everywhere (today's colours) so migration changes nothing; the per-app accents proposed in the design note are a one-line change per app once the owner chooses.
- **Found, not fixed (needs a decision, see token-audit.md):** in the light theme, status tone colours as text on their tinted container are under 4.5:1 (accent, success, warning, danger, info, neutral). They come from shared web tokens. A test pins the list so it can only shrink; story 10.1 decides.
- **WIP branch:** `wip/mobile-ui-refresh` was not merged or consulted for code; nothing in this change comes from it.

### Story 2.1: i18n infrastructure (done, verified by tests and by running the CI checks locally)
How-to: [i18n-howto.md](./i18n-howto.md).
- **Catalogues**: one typed JSON catalogue per app plus the shared design-system one (`AdminStrings`, `CustomerStrings`, `DriverStrings`, `LpgStrings`), English fallback, placeholders and plurals, each with a `LocalizationsDelegate`; generated files committed (a `.gitignore` exception, since the repo ignores `*.g.dart`). Each app seeds only its app title; **no existing string was moved** (stories 2.4 to 2.7).
- **Runtime locale switch plumbing**: `LpgCatalogueDelegate` and `lpgLocaleProvider`, watched by each app's `MaterialApp.router`; Flutter's own widget text is switched with it. **English only at launch**: each app's `supportedLocales` is `[Locale('en')]`, so the unreviewed Hindi test data cannot appear.
- **CI**: new job `i18n` in `mobile-ci.yml` runs `tools/check_catalogues.sh` (generated code up to date; no stray keys in a translation, which the generator would otherwise drop silently) and the `tools/i18n_lint` package (its own tests, then the hardcoded-string lint against a baseline of 832 strings in 107 files; a file may never go up). Negative case verified by hand: adding a string made the lint exit 1 with the file and line.
- **Not verified**: the new CI job itself has not run on GitHub (only its commands, locally, on Flutter 3.47.9).
- **Merge-order note**: the async-state PR adds friendly error copy in `design_system` (`lpg_error_copy.dart`, `lpg_async_view.dart`) as English literals. If it merges after this PR, the lint will flag those files; run `dart run bin/check.dart --root ../.. --update --allow-increase` once at that merge (they move into the catalogue in story 2.4).
- **Decision recorded:** languages are compiled in (no deferred loading); the lint counts per file, not per line, so editing around an old string does not trip it.

### Stories 3.1 to 3.4: async states (done, verified by tests; stacked on story 0.4's branch)
- **3.1 `LpgAsyncView` and `SliverLpgAsyncView`** (`design_system`): skeleton until the first answer (and its quiet retry), friendly error with Retry, empty state, data kept through refreshes and failed refreshes with a one-line notice, optional offline notice, scrollable-body support, and banner and scrollable error builders. Built on `whenQuiet` from story 0.4.
- **3.2 Error taxonomy** (`core`): `ErrorKind` (offline, busy, signed out, forbidden, agency blocked, not found, rejected, server, unknown) classified from the backend's real `error_code` values and the client's transport codes; a support code is shown small only where the message cannot say more. Friendly English copy per kind in `LpgErrorCopy`; the server's own sentence is never shown. `FailureCarrier` and `FailureException` moved to `core` (still exported by `api_client`). Copy reviewed by the `lpg-domain-expert` agent; its changes were applied and its per-app variants are recorded in TASKS.md.
- **3.3 Skeleton blocks** (`LpgSkeletonGroup`, `LpgSkeletonHero`, `LpgSkeletonTileGrid`, `LpgSkeletonCard`): one shimmer per group, inside a repaint boundary, stopped under reduce motion; used so the Admin dashboard, Customer home and Driver Today skeletons match their real layouts. **Shimmer cost was checked structurally by tests, not measured on a device** (no device here; story 0.3 owns the baseline).
- **3.4 Startup and auth gating**: `AuthController.whenSettled` and `ApiClient(waitForSession:)`; every request except the `/auth/*` endpoints waits until the start-up restore has decided the session, then carries the token. Wired in all three apps. The quiet single retry and its sequence tests are story 0.4's.
- **Dashboards converted:** Admin (two sections), Customer (balance hero, recent orders), Driver Today. Remaining AsyncValue sites: **68 in 50 files**, listed in TASKS.md (the plan's 129 also counted `Result.when`).
- **Decision recorded:** the Customer balance hero keeps its own-colour spinner while loading (grey placeholders clash with the gradient); the notice for a failed refresh is off on the Driver Today screen (the shell already shows the offline banner, and the pull-to-refresh list must stay the direct child).
- **Found, not fixed (in TASKS.md):** provider state survives sign-out (possible previous-user data on a shared phone); per-app wording variants; the Driver's cache reader surfaces raw `DioException`s.

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

### First visible screen change (Admin dashboard)

Two new design-system components, checked on the emulator with hot reload and covered by widget tests: `LpgHeroStats` replaces the "3 delivered • 0 failed • 2 to approve" sentence in the hero with three figures under their own labels, and `LpgMetricTile` gives the order and money tiles a heavy tabular figure plus a solid tone bar down the left edge when a tile needs attention (the caption says why, so colour is not the only signal). Admin's `MetricTile` is now a thin wrapper. 

**Customer Home and Driver Today (same pattern).** Driver Today: the Delivered / Remaining / Failed strip now sits inside the route hero (the separate row of three tiles is gone), the next-stop card carries a large "Open this stop" button as the screen's one primary action, and cash in hand is a metric tile placed after the next stop. Customer Home: the cylinder-balance hero shows "On the way" and "Orders placed" counts once the customer has ordered. Both were checked on the emulator (Driver signed in as the E2E driver, whose seeded in-progress route gives a real route to look at).

**4.3c, first part.** Customer Home's recent orders now use the shared grouped list with a status chip on each row (the same look as the Orders tab), and the order number alone as the title so a long chip does not wrap it. A metric tile's caption takes the tone colour only when the tile needs attention; otherwise it is secondary text, because a blue caption on a calm tile read like a link. Still the old look: the quick-action tiles, the live-order card, section headers, the timeline, and there are no small charts yet.

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
