# STATUS — Phase 5: Flutter Application Foundations

**Feature:** 05-flutter-application-foundations
**Plan:** [PLAN.md](./PLAN.md) · **Tasks:** [TASKS.md](./TASKS.md)

---

## Status

**COMPLETE — 17/18 tracked tasks verified**, 1 residual (CI-runner confirmation, not a blocker — see "Still Open"). Started and finished 2026-08-09, in a single continuous session, immediately after ADR-033 closed out, on explicit instruction.

## Progress

| Area | Complete | State |
|---|---|---|
| A — Encrypted Drift Database | 5/5 | ✅ Verified |
| B — Verification | 5/5 | ✅ Verified |
| C — Driver App Wiring | 3/3 | ✅ Verified |
| D — Documentation | 4/4 | ✅ Verified |
| E — Full Validation | 1/2 | 🔶 Local green; CI-runner confirmation pending |

## What Was Built

### Area A/B — `DriftLocalDatabase`

`mobile/packages/local_storage` now has a real, SQLCipher-encrypted Drift/SQLite implementation of the `LocalDatabase` interface that Phase 1 left as a documented placeholder. One foundation table, `SchemaMetadata` (key/value) — proves the pattern, not a preview of Phase 11's real schema.

**A genuine ecosystem trap, found and worked around, not just noted:** `sqlcipher_flutter_libs` — the obvious dependency — resolves to `0.7.0+eol` today; its own README says it "no longer does anything" because `package:sqlite3` moved to Dart's build-hooks system for encryption support in its v3.x line, which the current `drift` release now requires. The fix: `hooks.user_defines.sqlite3.source: sqlcipher` in both `local_storage/pubspec.yaml` and `driver_app/pubspec.yaml` (hooks resolve against whichever package is actually the build root). Full reasoning and alternatives considered: **ADR-034**.

**Encryption is verified, not assumed** — 7 tests in `local_storage/test/drift_local_database_test.dart`, including two that prove the encryption itself rather than just that a passphrase was configured:
- The raw on-disk bytes don't start with SQLite's plaintext magic header and don't contain an inserted plaintext value anywhere.
- Opening the same file with the wrong key throws a genuine SQLCipher HMAC page-decryption failure (`hmac check failed for pgno=1` — a real cryptographic failure surfaced in the test log, not simulated).

**A real bug found and fixed along the way:** the first version of `open()` let a failed sanity-check query leave the background isolate's executor un-closed on a bad-key failure, orphaning a file lock — surfaced by the wrong-key test's own cleanup repeatedly failing on Windows (which, unlike POSIX, refuses to delete an open file). Fixed in `DriftLocalDatabase.open()` itself (explicit `close()` on the failure path before rethrowing), not worked around by adding a delay in the test.

### Area C — Driver App Wiring

`driver_app/lib/main.dart` now opens a real `DriftLocalDatabase` before the first frame and overrides a new `localDatabaseProvider` (Riverpod) with it — the rest of the app can assume the database is always ready. The Customer App is untouched: no `local_storage` dependency, no Drift wiring, per ADR-008 (offline-first is Driver-App-only; the Customer App uses simple cache-and-refresh).

### Area D — Documentation

**ADR-034** records the SQLCipher/Drift decision, the `sqlcipher_flutter_libs` EOL trap, the verification approach, and the executor-leak bug. `local_storage/lib/local_storage.dart`'s library doc comment updated (Phase 5 done; sync queue/conflict resolution still Phase 11).

## Verification (2026-08-09)

Melos itself (`dart pub global run melos bootstrap`) did not recognize `mobile/` as a workspace with the installed Melos 8.2.2 — a tooling-version mismatch against whatever Melos version this repo's `melos.yaml` was originally written for. **Not a blocker**: `.github/workflows/mobile-ci.yml` does not use Melos either — it runs `flutter pub get` / `dart format --set-exit-if-changed .` / `flutter analyze` / `flutter test` directly per package via a matrix. Every check below was run exactly that way, per package, matching CI precisely.

| Package | `pub get` | `dart format --set-exit-if-changed` | `flutter analyze` | `flutter test` |
|---|---|---|---|---|
| `packages/core` | ✅ | ✅ | ✅ No issues | ✅ 3/3 |
| `packages/design_system` | ✅ | ✅ | ✅ No issues | ✅ 4/4 |
| `packages/local_storage` | ✅ | ✅ | ✅ No issues | ✅ **7/7** (was 1; +6 for `DriftLocalDatabase`) |
| `apps/customer_app` | ✅ | ✅ | ✅ No issues | ✅ 2/2 |
| `apps/driver_app` | ✅ | ✅ | ✅ No issues | ✅ 2/2 |

**18/18 Flutter tests passing** across all 5 packages/apps (was 12 before this phase), 0 regressions.

## Still Open (not blockers)

- **CI-runner confirmation** — the SQLCipher build-hook was verified locally on Windows (`flutter 3.44.2`, `dart 3.12.2`) but not yet observed green on the actual `ubuntu-latest` runner `.github/workflows/mobile-ci.yml` uses. The hook resolved and downloaded correctly without any experimental flag being explicitly enabled locally, but Linux is a different target platform for the binary it fetches. Flagged in ADR-034; remove this line once the next CI run of this change confirms it.
- **Sync queue + conflict resolution** (`05-mobile-architecture.md` §3) — explicitly Phase 11 work, per `local_storage`'s own doc comment and this phase's `PLAN.md`. Nothing to queue yet; building it now would be speculative.
- **`mobile/packages/api_client`, `auth`, `sync_engine`** — still not created; arrive with Phase 6 (Authentication) and Phase 11 respectively, per `knowledge/12-current-status.md`'s existing Known Risks entry.
- Every business feature (assigned deliveries, OTP verification, proof-of-delivery capture, order history) — arrives with the modules that own them, unchanged from this phase's explicit exclusions in `PLAN.md`.

## Last Updated

2026-08-09 — phase complete, all areas verified locally; CI-runner confirmation the one open item, tracked above.
