# TASKS — Phase 5: Flutter Application Foundations

**Feature:** 05-flutter-application-foundations
**Plan:** [PLAN.md](./PLAN.md)

---

## Area A — Encrypted Drift Database

- [x] A1. Research the current `sqlite3`/`drift`/SQLCipher ecosystem state (`sqlcipher_flutter_libs` turned out to be EOL/obsolete for `sqlite3` v3.x; the replacement is `package:sqlite3`'s build-hook `source` selection).
- [x] A2. Add `drift`, `sqlite3`, `path`, `path_provider`, `flutter_secure_storage` to `local_storage/pubspec.yaml`; `drift_dev`/`build_runner` as dev dependencies.
- [x] A3. Define the `SchemaMetadata` foundation table and generate Drift code (`dart run build_runner build`).
- [x] A4. Implement `DriftLocalDatabase` (SQLCipher key generation via `Random.secure()`, storage via `flutter_secure_storage`, injectable key/file resolution for testability).
- [x] A5. Configure `hooks.user_defines.sqlite3.source: sqlcipher` in both `local_storage/pubspec.yaml` and `driver_app/pubspec.yaml`.

## Area B — Verification

- [x] B1. Test: open/write/read/close round-trip with the correct key.
- [x] B2. Test: data persists correctly across a close-and-reopen with the same key.
- [x] B3. Test: the on-disk file is not a readable plaintext SQLite file (magic-header check + raw-byte content check) — the actual proof of encryption at rest.
- [x] B4. Test: opening the same file with the wrong key fails with a genuine SQLCipher HMAC decryption error.
- [x] B5. Found and fixed a real bug during B4: a failed sanity-check query left the background isolate's executor un-closed, orphaning a file lock. Fixed in `DriftLocalDatabase.open()`, not worked around in the test.

## Area C — Driver App Wiring

- [x] C1. Add `localDatabaseProvider` (Riverpod) to `driver_app`, defaulting to a loud `UnimplementedError` if never overridden.
- [x] C2. Wire `main()` to open a real `DriftLocalDatabase` before the first frame and override the provider with it.
- [x] C3. Confirm the Customer App is untouched — no `local_storage` dependency, no Drift wiring, per ADR-008.

## Area D — Documentation

- [x] D1. **ADR-034** — SQLCipher-encrypted Drift via `package:sqlite3`'s build-hook source selection.
- [x] D2. Update `local_storage/lib/local_storage.dart`'s library doc comment (Phase 5 done, Phase 11 still ahead).
- [x] D3. This feature's `PLAN.md`/`TASKS.md`/`STATUS.md`.
- [x] D4. Update `planning/current_phase.md` and `knowledge/12-current-status.md`.

## Area E — Full Validation

- [x] E1. `dart format --set-exit-if-changed .`, `flutter analyze`, `flutter test` — all 5 packages/apps, matching `.github/workflows/mobile-ci.yml`'s matrix.
- [ ] E2. Confirm green on the actual `ubuntu-latest` CI runner (not yet observed — the hooks-based SQLCipher build was only verified locally on Windows; flagged as a residual risk in ADR-034 and STATUS.md until the next CI run confirms it).
