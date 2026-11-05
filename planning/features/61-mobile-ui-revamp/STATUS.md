# Status: Mobile UI/UX Revamp, i18n, Device Control and Alert Sounds

**Release R1 in progress (plan version 5, 2026-11-05).** Stories are implemented one per PR, stacked on the plan branch `docs/mobile-ui-revamp-plan` (PR #122). Tick state is in [TASKS.md](./TASKS.md).

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

### Stories 3.1 to 3.4: async states (done, verified by tests; stacked on story 0.4's branch)
- **3.1 `LpgAsyncView` and `SliverLpgAsyncView`** (`design_system`): skeleton until the first answer (and its quiet retry), friendly error with Retry, empty state, data kept through refreshes and failed refreshes with a one-line notice, optional offline notice, scrollable-body support, and banner and scrollable error builders. Built on `whenQuiet` from story 0.4.
- **3.2 Error taxonomy** (`core`): `ErrorKind` (offline, busy, signed out, forbidden, agency blocked, not found, rejected, server, unknown) classified from the backend's real `error_code` values and the client's transport codes; a support code is shown small only where the message cannot say more. Friendly English copy per kind in `LpgErrorCopy`; the server's own sentence is never shown. `FailureCarrier` and `FailureException` moved to `core` (still exported by `api_client`). Copy reviewed by the `lpg-domain-expert` agent; its changes were applied and its per-app variants are recorded in TASKS.md.
- **3.3 Skeleton blocks** (`LpgSkeletonGroup`, `LpgSkeletonHero`, `LpgSkeletonTileGrid`, `LpgSkeletonCard`): one shimmer per group, inside a repaint boundary, stopped under reduce motion; used so the Admin dashboard, Customer home and Driver Today skeletons match their real layouts. **Shimmer cost was checked structurally by tests, not measured on a device** (no device here; story 0.3 owns the baseline).
- **3.4 Startup and auth gating**: `AuthController.whenSettled` and `ApiClient(waitForSession:)`; every request except the `/auth/*` endpoints waits until the start-up restore has decided the session, then carries the token. Wired in all three apps. The quiet single retry and its sequence tests are story 0.4's.
- **Dashboards converted:** Admin (two sections), Customer (balance hero, recent orders), Driver Today. Remaining AsyncValue sites: **68 in 50 files**, listed in TASKS.md (the plan's 129 also counted `Result.when`).
- **Decision recorded:** the Customer balance hero keeps its own-colour spinner while loading (grey placeholders clash with the gradient); the notice for a failed refresh is off on the Driver Today screen (the shell already shows the offline banner, and the pull-to-refresh list must stay the direct child).
- **Found, not fixed (in TASKS.md):** provider state survives sign-out (possible previous-user data on a shared phone); per-app wording variants; the Driver's cache reader surfaces raw `DioException`s.

## Not done
Everything else in TASKS.md.
