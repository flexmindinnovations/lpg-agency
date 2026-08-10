/// Local storage foundation for offline-capable features.
///
/// Phase 5 adds the encrypted Drift/SQLite database itself
/// (`DriftLocalDatabase`, ADR-034); the sync queue and conflict resolution
/// remain Phase 11 work (D-24, ADR-008), landing once the Driver App has
/// real offline features to drive them — the schema here is deliberately
/// just a foundation table, not business data.
///
/// One decision is already fixed by the architecture and must keep holding
/// as the schema grows: every mutation is written locally first and queued
/// for sync; the UI is optimistic.
library;

export 'src/local_database.dart';
export 'src/drift/app_database.dart';
export 'src/drift_local_database.dart';
