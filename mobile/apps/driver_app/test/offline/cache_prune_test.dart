// The Driver app's read cache forgets rows nobody has refreshed for two weeks,
// on a real (encrypted) database, when the cache is first used.
import 'dart:io';

import 'package:api_client/api_client.dart';
import 'package:auth/auth.dart';
import 'package:core/core.dart';
import 'package:driver_app/src/auth_provider.dart';
import 'package:driver_app/src/local_database_provider.dart';
import 'package:driver_app/src/offline/cached_resource.dart';
import 'package:drift/drift.dart' show Value;
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:local_storage/local_storage.dart';
import 'package:path/path.dart' as p;

const _me = Principal(
  userId: 'driver-1',
  tenantId: 't1',
  role: 'driver',
  permissions: {},
);

/// A repository whose start-up restore finds [session] (or nothing), and which
/// signs [_me] in when asked.
class _Repo implements AuthRepository {
  _Repo({this.session});

  final Principal? session;

  @override
  String? accessToken;

  @override
  Future<Result<Principal>> restoreSession() async => session != null
      ? Success(session!)
      : const FailureResult(Failure(message: 'none', errorCode: 'NO_SESSION'));

  @override
  Future<Result<Principal>> login({
    required String email,
    required String password,
  }) async => const Success(_me);

  @override
  Future<Result<void>> requestOtp({
    required String tenantId,
    required String phoneNumber,
  }) async => throw UnimplementedError();

  @override
  Future<Result<Principal>> verifyOtp({
    required String tenantId,
    required String phoneNumber,
    required String code,
  }) async => throw UnimplementedError();

  @override
  Future<Result<void>> requestPasswordReset({required String email}) async =>
      throw UnimplementedError();

  @override
  Future<Result<void>> confirmPasswordReset({
    required String resetToken,
    required String newPassword,
  }) async => throw UnimplementedError();

  @override
  Future<void> logout() async {}
}

/// A real encrypted database with rows for the given owners and ages, and a
/// container wired to [auth].
class _Harness {
  _Harness._(this.dir, this.db);

  final Directory dir;
  final DriftLocalDatabase db;

  static Future<_Harness> open() async {
    final dir = Directory.systemTemp.createTempSync('cache_prune_');
    final db = DriftLocalDatabase(
      loadEncryptionKey: () async => 'test-passphrase-0123456789abcdef',
      resolveFile: () async => File(p.join(dir.path, 'test.sqlite')),
    );
    await db.open();
    return _Harness._(dir, db);
  }

  Future<void> close() async {
    await db.close();
    dir.deleteSync(recursive: true);
  }

  Future<void> insert(String owner, String id, Duration age) => db.database
      .into(db.database.cachedResources)
      .insert(
        CachedResourcesCompanion.insert(
          resourceType: 'route_active',
          resourceId: id,
          jsonPayload: '{}',
          ownerId: Value(owner),
          updatedAt: Value(DateTime.now().subtract(age)),
        ),
      );

  Future<Set<String>> ids() async => {
    for (final r in await db.database.select(db.database.cachedResources).get())
      r.resourceId,
  };

  ProviderContainer container(AuthController auth) {
    final c = ProviderContainer(
      overrides: [
        localDatabaseProvider.overrideWithValue(db),
        authControllerProvider.overrideWithValue(auth),
      ],
    );
    return c;
  }
}

Future<void> _settle() =>
    Future<void>.delayed(const Duration(milliseconds: 300));

void main() {
  test('stale cache rows are pruned when the cache is first used; fresh ones '
      'stay', () async {
    final dir = Directory.systemTemp.createTempSync('cache_prune_');
    final db = DriftLocalDatabase(
      loadEncryptionKey: () async => 'test-passphrase-0123456789abcdef',
      resolveFile: () async => File(p.join(dir.path, 'test.sqlite')),
    );
    await db.open();
    addTearDown(() async {
      await db.close();
      dir.deleteSync(recursive: true);
    });

    Future<void> insert(String id, DateTime updatedAt) => db.database
        .into(db.database.cachedResources)
        .insert(
          CachedResourcesCompanion.insert(
            resourceType: 'route_active',
            resourceId: id,
            jsonPayload: '{}',
            ownerId: const Value('driver-9'),
            updatedAt: Value(updatedAt),
          ),
        );
    await insert('stale', DateTime.now().subtract(const Duration(days: 40)));
    await insert('fresh', DateTime.now().subtract(const Duration(days: 2)));

    final container = ProviderContainer(
      overrides: [
        localDatabaseProvider.overrideWithValue(db),
        authControllerProvider.overrideWithValue(AuthController(_Repo())),
      ],
    );
    addTearDown(container.dispose);

    expect(container.read(resourceCacheProvider), isNotNull);
    await Future<void>.delayed(const Duration(milliseconds: 300));

    final left = {
      for (final r
          in await db.database.select(db.database.cachedResources).get())
        r.resourceId,
    };
    expect(left, {'fresh'});
  });

  group('rows of drivers who have signed out of this phone', () {
    test('once a driver is signed in, other drivers\' rows older than two '
        'days go; their own and recent ones stay', () async {
      final h = await _Harness.open();
      addTearDown(h.close);
      await h.insert('driver-1', 'mine', const Duration(days: 5));
      await h.insert('driver-2', 'other-old', const Duration(days: 5));
      await h.insert('driver-2', 'other-recent', const Duration(hours: 1));
      final auth = AuthController(_Repo(session: _me));
      await _settle(); // the start-up restore signs driver-1 in
      final container = h.container(auth);
      addTearDown(container.dispose);

      container.read(resourceCacheProvider);
      await _settle();

      expect(await h.ids(), {'mine', 'other-recent'});
    });

    test('a session still being restored does not make the returning driver '
        'look like a stranger', () async {
      final h = await _Harness.open();
      addTearDown(h.close);
      await h.insert('driver-1', 'returning', const Duration(days: 5));
      final auth = AuthController(_Repo()); // nobody signed in
      await _settle();
      final container = h.container(auth);
      addTearDown(container.dispose);

      container.read(resourceCacheProvider);
      await _settle();

      expect(await h.ids(), {'returning'});
    });

    test('it runs when a driver signs in after the cache was built', () async {
      final h = await _Harness.open();
      addTearDown(h.close);
      await h.insert('driver-2', 'previous-driver', const Duration(days: 5));
      final auth = AuthController(_Repo());
      await _settle();
      final container = h.container(auth);
      addTearDown(container.dispose);
      container.read(resourceCacheProvider);
      await _settle();
      expect(await h.ids(), {
        'previous-driver',
      }, reason: 'nobody signed in yet');

      await auth.login(email: 'driver1@agency.test', password: 'x');
      await _settle();

      expect(await h.ids(), isEmpty);
    });
  });
}
