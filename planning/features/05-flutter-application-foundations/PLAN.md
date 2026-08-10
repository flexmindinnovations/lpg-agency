# PLAN — Phase 5: Flutter Application Foundations

**Feature:** 05-flutter-application-foundations

---

## Scope

Per `docs/implementation/roadmap.md`'s phase table: **"Melos workspace, shared packages, Riverpod, go_router, Drift schema + encrypted storage, both app shells."**

Most of this was already delivered under Phase 1's execution (the Melos workspace, both app shells with Riverpod/go_router wired, the `core`/`design_system`/`local_storage` package scaffolds, CI). What Phase 1 deliberately left open — `local_storage/lib/src/local_database.dart`'s own doc comment said so explicitly — was the Drift schema itself and encryption at rest. **This phase closes exactly that gap and nothing more.**

## In Scope

- `DriftLocalDatabase` — a real, SQLCipher-encrypted Drift/SQLite implementation of the existing `LocalDatabase` interface (`docs/architecture/05-mobile-architecture.md` §7).
- One foundation table (`SchemaMetadata`) proving the encrypted-open/read/write/close pattern works end to end — not business data.
- Wiring `DriftLocalDatabase` into the Driver App (`main.dart`, opened before the first frame, exposed via a Riverpod provider) — the Customer App does not get it, per ADR-008 (offline-first is Driver-App-only).
- Genuine encryption verification: tests proving the on-disk file isn't a readable plaintext SQLite file, and that the wrong key fails to open it — not just that a passphrase was configured.
- ADR-034 documenting the SQLCipher/Drift implementation, including a real ecosystem trap (`sqlcipher_flutter_libs` is now an EOL no-op) discovered and resolved during implementation.

## Explicitly Out of Scope

- **The sync queue and conflict resolution** (`05-mobile-architecture.md` §3) — `local_storage`'s own doc comment already scoped this to Phase 11, once the Driver App has real offline features (delivery confirmations, POD capture) to actually drive a sync queue. Building a generic queue now, with nothing to queue, would be speculative infrastructure.
- **`mobile/packages/api_client`, `auth`, `sync_engine`** — per `knowledge/12-current-status.md`'s existing Known Risks entry, these have no content until Phase 6 (Authentication, for `auth` and the first real `api_client` consumer) and Phase 11 (`sync_engine`).
- **Any business feature** — Customer/Order/Delivery/Inventory screens, assigned-delivery lists, OTP verification, proof-of-delivery capture. The Driver App and Customer App remain placeholder shells; only their local-storage foundation changes.
- **`flutter_secure_storage` for auth tokens** — `05-mobile-architecture.md` §7 also calls for this, but it's an `auth`-package concern (Phase 6), not `local_storage`'s. `local_storage` does use `flutter_secure_storage` in this phase, but only to hold the SQLCipher passphrase — a distinct, narrower use.

## Architectural Constraints (already decided, not reopened here)

- **ADR-006** — Flutter, single codebase, shared packages + per-app targets.
- **ADR-008** — full offline-first (local DB) for the Driver App only; simple cache-and-refresh for the Customer App.
- **`05-mobile-architecture.md` §5–§7** — Riverpod (code-gen flavor), go_router, Drift/SQLite encrypted via SQLCipher, `flutter_secure_storage` for anything secret.

## Verification Plan

- `dart format --set-exit-if-changed .`, `flutter analyze`, `flutter test` in every one of the 5 packages/apps — matching `.github/workflows/mobile-ci.yml`'s matrix exactly, run locally per package (Melos itself was not usable locally — see STATUS.md — so CI's actual per-package commands were run directly instead).
- Encryption is verified, not assumed: a dedicated test suite proves a real SQLCipher HMAC failure on a wrong key, and that the raw file bytes are neither the standard SQLite magic header nor a plaintext match for known-inserted data.
