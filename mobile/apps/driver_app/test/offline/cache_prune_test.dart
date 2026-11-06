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

class _NoSession implements AuthRepository {
  @override
  String? accessToken;

  @override
  Future<Result<Principal>> restoreSession() async =>
      const FailureResult(Failure(message: 'none', errorCode: 'NO_SESSION'));

  @override
  Future<Result<Principal>> login({
    required String email,
    required String password,
  }) async => throw UnimplementedError();

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
        authControllerProvider.overrideWithValue(AuthController(_NoSession())),
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
}
