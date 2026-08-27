import 'package:drift/drift.dart';

part 'app_database.g.dart';

/// Foundation table only — proves the encrypted-at-rest Drift pattern works
/// end to end (open, migrate, read, write, wrong-key-fails).
class SchemaMetadata extends Table {
  TextColumn get key => text()();
  TextColumn get value => text()();

  @override
  Set<Column> get primaryKey => {key};
}

/// Stores offline mutations to be synchronized with the backend.
/// Enforces ordered execution and idempotency for offline operations.
class SyncOperations extends Table {
  TextColumn get id => text()();
  TextColumn get type => text()();
  TextColumn get payload => text()();
  TextColumn get status => text().withDefault(const Constant('pending'))();
  DateTimeColumn get createdAt => dateTime().withDefault(currentDateAndTime)();
  TextColumn get errorMessage => text().nullable()();
  TextColumn get idempotencyKey => text().unique()();

  @override
  Set<Column> get primaryKey => {id};
}

/// Generic offline read cache — one row per `(resourceType, resourceId)`
/// pair, e.g. `('order', '<uuid>')` or `('ledger_balance', '<customerId>')`.
/// A single table instead of one per domain (orders/profile/invoices/...)
/// keeps schema churn low: every screen's provider reads this cache-first,
/// then overwrites the row on a successful API refresh, and adding a new
/// cached resource type never needs a migration.
class CachedResources extends Table {
  TextColumn get resourceType => text()();
  TextColumn get resourceId => text()();
  TextColumn get jsonPayload => text()();
  DateTimeColumn get updatedAt => dateTime().withDefault(currentDateAndTime)();

  @override
  Set<Column> get primaryKey => {resourceType, resourceId};
}

@DriftDatabase(tables: [SchemaMetadata, SyncOperations, CachedResources])
class AppDatabase extends _$AppDatabase {
  AppDatabase(super.executor);

  @override
  int get schemaVersion => 3;

  @override
  MigrationStrategy get migration => MigrationStrategy(
    onCreate: (m) async {
      await m.createAll();
    },
    onUpgrade: (m, from, to) async {
      if (from < 2) {
        await m.createTable(syncOperations);
      }
      if (from < 3) {
        await m.createTable(cachedResources);
      }
    },
  );
}
