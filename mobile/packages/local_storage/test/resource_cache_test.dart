import 'dart:io';

import 'package:drift/drift.dart' show Value;
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

  test('delete evicts one row and leaves the rest', () async {
    await cache.write('order', 'a', {'n': 1});
    await cache.write('order', 'b', {'n': 2});

    await cache.delete('order', 'a');

    expect(await cache.read('order', 'a'), isNull);
    expect(await cache.read('order', 'b'), {'n': 2});
  });

  test('clear drops every row', () async {
    await cache.write('order', 'a', {'n': 1});
    await cache.write('invoice', 'b', {'n': 2});

    await cache.clear();

    expect(await cache.read('order', 'a'), isNull);
    expect(await cache.read('invoice', 'b'), isNull);
  });

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

  group('owner scoping (a phone shared by two people)', () {
    test('one user never reads another user\'s cached data', () async {
      var owner = 'driver-1';
      final scoped = ResourceCache(db.database, owner: () => owner);
      await scoped.write('route_active', 'current', {'id': 'route-of-1'});

      owner = 'driver-2';
      expect(await scoped.read('route_active', 'current'), isNull);
      expect(await scoped.readAll('route_active'), isEmpty);

      await scoped.write('route_active', 'current', {'id': 'route-of-2'});
      expect(await scoped.read('route_active', 'current'), {
        'id': 'route-of-2',
      });

      owner = 'driver-1';
      expect(await scoped.read('route_active', 'current'), {
        'id': 'route-of-1',
      });
    });

    test('evicting a row only evicts the signed-in user\'s', () async {
      var owner = 'driver-1';
      final scoped = ResourceCache(db.database, owner: () => owner);
      await scoped.write('route_active', 'current', {'id': 'a'});
      owner = 'driver-2';
      await scoped.write('route_active', 'current', {'id': 'b'});

      await scoped.delete('route_active', 'current');

      owner = 'driver-1';
      expect(await scoped.read('route_active', 'current'), {'id': 'a'});
    });

    test('clear (an explicit log out) removes every user\'s rows', () async {
      var owner = 'driver-1';
      final scoped = ResourceCache(db.database, owner: () => owner);
      await scoped.write('route_active', 'current', {'id': 'a'});
      owner = 'driver-2';
      await scoped.write('route_active', 'current', {'id': 'b'});

      await scoped.clear();

      expect(await scoped.read('route_active', 'current'), isNull);
      owner = 'driver-1';
      expect(await scoped.read('route_active', 'current'), isNull);
    });
  });

  group('pruneStale', () {
    final longAgo = DateTime.now().subtract(const Duration(days: 40));
    final lastWeek = DateTime.now().subtract(const Duration(days: 7));

    Future<void> insert(String owner, String id, DateTime updatedAt) => db
        .database
        .into(db.database.cachedResources)
        .insert(
          CachedResourcesCompanion.insert(
            resourceType: 'route_active',
            resourceId: id,
            jsonPayload: '{"id": "$id"}',
            ownerId: Value(owner),
            updatedAt: Value(updatedAt),
          ),
        );

    Future<Set<String>> ids() async => {
      for (final r
          in await db.database.select(db.database.cachedResources).get())
        r.resourceId,
    };

    test('deletes rows not written for two weeks, whoever owns them', () async {
      await insert('driver-1', 'old-1', longAgo);
      await insert('driver-2', 'old-2', longAgo);
      await insert('driver-1', 'recent', lastWeek);

      final removed = await cache.pruneStale();

      expect(removed, 2);
      expect(await ids(), {'recent'});
    });

    test(
      'keeps a row that was just refreshed, even if it started old',
      () async {
        await insert('driver-1', 'r', longAgo);
        await ResourceCache(
          db.database,
          owner: () => 'driver-1',
        ).write('route_active', 'r', {'id': 'r', 'fresh': true});

        expect(await cache.pruneStale(), 0);
        expect(await ids(), {'r'});
      },
    );

    test('the retention is adjustable', () async {
      await insert('driver-1', 'a-week-old', lastWeek);

      expect(await cache.pruneStale(), 0);
      expect(await cache.pruneStale(olderThan: const Duration(days: 3)), 1);
    });

    test('an empty cache is fine', () async {
      expect(await cache.pruneStale(), 0);
    });
  });

  group('pruneOtherOwners (drivers who have signed out of this phone)', () {
    final threeDaysAgo = DateTime.now().subtract(const Duration(days: 3));
    final lastHour = DateTime.now().subtract(const Duration(hours: 1));

    Future<void> insert(String owner, String id, DateTime updatedAt) => db
        .database
        .into(db.database.cachedResources)
        .insert(
          CachedResourcesCompanion.insert(
            resourceType: 'route_active',
            resourceId: id,
            jsonPayload: '{"id": "$id"}',
            ownerId: Value(owner),
            updatedAt: Value(updatedAt),
          ),
        );

    Future<Set<String>> ids() async => {
      for (final r
          in await db.database.select(db.database.cachedResources).get())
        r.resourceId,
    };

    ResourceCache signedInAs(String? who) =>
        ResourceCache(db.database, owner: () => who);

    test('deletes other users\' rows older than two days', () async {
      await insert('driver-1', 'mine-old', threeDaysAgo);
      await insert('driver-2', 'theirs-old', threeDaysAgo);
      await insert('driver-3', 'theirs-old-too', threeDaysAgo);

      final removed = await signedInAs('driver-1').pruneOtherOwners();

      expect(removed, 2);
      expect(await ids(), {'mine-old'}, reason: 'own rows are never touched');
    });

    test(
      'keeps another user\'s recent rows, so a shift change can come back',
      () async {
        await insert('driver-2', 'theirs-recent', lastHour);

        expect(await signedInAs('driver-1').pruneOtherOwners(), 0);
        expect(await ids(), {'theirs-recent'});
      },
    );

    test(
      'does nothing while nobody is signed in (a session being restored)',
      () async {
        await insert('driver-1', 'returning-driver', threeDaysAgo);

        expect(await signedInAs(null).pruneOtherOwners(), 0);
        expect(await ResourceCache(db.database).pruneOtherOwners(), 0);
        expect(await ids(), {'returning-driver'});
      },
    );

    test(
      'rows written with no one signed in count as someone else\'s',
      () async {
        await insert('', 'anonymous', threeDaysAgo);

        expect(await signedInAs('driver-1').pruneOtherOwners(), 1);
      },
    );

    test('the grace period is adjustable', () async {
      await insert('driver-2', 'theirs', threeDaysAgo);

      expect(
        await signedInAs('driver-1')
            .pruneOtherOwners(olderThan: const Duration(days: 5)),
        0,
      );
      expect(
        await signedInAs('driver-1')
            .pruneOtherOwners(olderThan: const Duration(days: 1)),
        1,
      );
    });
  });
}
