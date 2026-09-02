/// Local storage foundation for offline-capable features.
///
/// Phase 5 added the encrypted Drift/SQLite database itself
/// (`DriftLocalDatabase`, ADR-034). Phase 26 (D-24, ADR-008) drives the
/// `SyncOperations` queue and `CachedResources` read cache from the Driver
/// App's real offline delivery flow; `sync_engine`'s `SyncCoordinator` owns
/// the drain/retry/conflict logic over these tables.
///
/// The architectural invariant: every mutation is written locally first and
/// queued for sync; the UI is optimistic.
library;

export 'src/local_database.dart';
export 'src/drift/app_database.dart';
export 'src/drift_local_database.dart';
export 'src/resource_cache.dart';
