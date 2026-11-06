// The v4 to v5 upgrade (story: owner-scoped queue and cache). A phone that
// already holds a queue must keep every unsent operation, and the read cache is
// rebuilt with its owner in the key.
import 'package:drift/native.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:local_storage/local_storage.dart';

void main() {
  test('upgrading from v4 keeps queued operations (unowned) and rebuilds the '
      'cache', () async {
    final db = AppDatabase(
      NativeDatabase.memory(
        setup: (raw) {
          raw.execute('''
            CREATE TABLE schema_metadata (key TEXT NOT NULL PRIMARY KEY, value TEXT NOT NULL);
          ''');
          raw.execute('''
            CREATE TABLE sync_operations (
              id TEXT NOT NULL PRIMARY KEY,
              type TEXT NOT NULL,
              payload TEXT NOT NULL,
              status TEXT NOT NULL DEFAULT 'pending',
              created_at INTEGER NOT NULL DEFAULT (strftime('%s','now')),
              error_message TEXT NULL,
              idempotency_key TEXT NOT NULL UNIQUE,
              retry_count INTEGER NOT NULL DEFAULT 0,
              last_attempt_at INTEGER NULL
            );
          ''');
          raw.execute('''
            CREATE TABLE cached_resources (
              resource_type TEXT NOT NULL,
              resource_id TEXT NOT NULL,
              json_payload TEXT NOT NULL,
              updated_at INTEGER NOT NULL DEFAULT (strftime('%s','now')),
              PRIMARY KEY (resource_type, resource_id)
            );
          ''');
          raw.execute(
            "INSERT INTO sync_operations (id, type, payload, idempotency_key) "
            "VALUES ('op-1', 'order_depart', '{}', 'key-1');",
          );
          raw.execute(
            "INSERT INTO cached_resources (resource_type, resource_id, json_payload) "
            "VALUES ('route_active', 'current', '{\"id\":\"old\"}');",
          );
          raw.execute('PRAGMA user_version = 4;');
        },
      ),
    );
    addTearDown(db.close);

    final ops = await db.select(db.syncOperations).get();
    expect(ops, hasLength(1), reason: 'an unsent delivery must survive');
    expect(ops.single.id, 'op-1');
    expect(ops.single.ownerId, isNull, reason: 'adopted by the next sign-in');

    final cache = ResourceCache(db, owner: () => 'driver-1');
    expect(await cache.read('route_active', 'current'), isNull);
    await cache.write('route_active', 'current', {'id': 'new'});
    expect(await cache.read('route_active', 'current'), {'id': 'new'});
  });
}
