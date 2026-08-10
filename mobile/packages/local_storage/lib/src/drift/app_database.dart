import 'package:drift/drift.dart';

part 'app_database.g.dart';

/// Foundation table only — proves the encrypted-at-rest Drift pattern works
/// end to end (open, migrate, read, write, wrong-key-fails). Real schema
/// (routes/stops, vehicle inventory snapshot, sync queue) is Phase 11 work,
/// once the Driver App's actual offline features exist to drive it.
class SchemaMetadata extends Table {
  TextColumn get key => text()();
  TextColumn get value => text()();

  @override
  Set<Column> get primaryKey => {key};
}

@DriftDatabase(tables: [SchemaMetadata])
class AppDatabase extends _$AppDatabase {
  AppDatabase(super.executor);

  @override
  int get schemaVersion => 1;
}
