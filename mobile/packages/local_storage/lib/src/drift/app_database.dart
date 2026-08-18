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

@DriftDatabase(tables: [SchemaMetadata, SyncOperations])
class AppDatabase extends _$AppDatabase {
  AppDatabase(super.executor);

  @override
  int get schemaVersion => 2;
  
  @override
  MigrationStrategy get migration => MigrationStrategy(
        onCreate: (m) async {
          await m.createAll();
        },
        onUpgrade: (m, from, to) async {
          if (from < 2) {
            await m.createTable(syncOperations);
          }
        },
      );
}
