import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:local_storage/local_storage.dart';
import 'package:path/path.dart' as p;

void main() {
  late Directory tempDir;
  late DriftLocalDatabase db;
  late ResourceCache cache;

  setUp(() async {
    tempDir = Directory.systemTemp.createTempSync('resource_cache_test_');
    db = DriftLocalDatabase(
      loadEncryptionKey: () async => 'test-passphrase-0123456789abcdef',
      resolveFile: () async => File(p.join(tempDir.path, 'test.sqlite')),
    );
    await db.open();
    cache = ResourceCache(db.database);
  });

  tearDown(() async {
    await db.close();
    for (var attempt = 0; attempt < 5; attempt++) {
      try {
        if (tempDir.existsSync()) tempDir.deleteSync(recursive: true);
        return;
      } catch (_) {
        if (attempt == 4) rethrow;
        await Future<void>.delayed(const Duration(milliseconds: 100));
      }
    }
  });

  test('read returns null for a resource never written', () async {
    expect(await cache.read('order', 'missing-id'), isNull);
  });

  test('write then read round-trips the JSON payload', () async {
    await cache.write('order', 'order-1', {'status': 'booked', 'total': 42});
    final result = await cache.read('order', 'order-1');
    expect(result, {'status': 'booked', 'total': 42});
  });

  test('write overwrites an existing row for the same key', () async {
    await cache.write('order', 'order-1', {'status': 'booked'});
    await cache.write('order', 'order-1', {'status': 'delivered'});
    final result = await cache.read('order', 'order-1');
    expect(result, {'status': 'delivered'});
  });

  test(
    'rows with different resourceType do not collide on the same id',
    () async {
      await cache.write('order', 'shared-id', {'kind': 'order'});
      await cache.write('invoice', 'shared-id', {'kind': 'invoice'});
      expect(await cache.read('order', 'shared-id'), {'kind': 'order'});
      expect(await cache.read('invoice', 'shared-id'), {'kind': 'invoice'});
    },
  );

  test(
    'readAll returns every row of one resourceType, most recent first',
    () async {
      // Drift's default DateTimeColumn stores unix-epoch seconds, not
      // milliseconds — the gap must exceed 1s or both rows round to the same
      // second and the ORDER BY desc tiebreak becomes insertion order.
      await cache.write('order', 'a', {'n': 1});
      await Future<void>.delayed(const Duration(seconds: 1, milliseconds: 100));
      await cache.write('order', 'b', {'n': 2});
      await cache.write('invoice', 'c', {'n': 3});

      final orders = await cache.readAll('order');
      expect(orders, [
        {'n': 2},
        {'n': 1},
      ]);
    },
  );
}
