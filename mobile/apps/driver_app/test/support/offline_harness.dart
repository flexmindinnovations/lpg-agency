import 'package:api_client/api_client.dart';
import 'package:driver_app/src/api_provider.dart';
import 'package:driver_app/src/offline/cached_resource.dart';
import 'package:driver_app/src/offline/sync_providers.dart';
import 'package:drift/native.dart';
import 'package:flutter_riverpod/misc.dart' show Override;
import 'package:local_storage/local_storage.dart';
import 'package:sync_engine/sync_engine.dart';

/// A real in-memory `SyncCoordinator` + `ResourceCache` for tests that
/// exercise the offline write path (Stage 4+). `apiClient` should carry a
/// fake `HttpClientAdapter` so enqueued ops sync against a stub.
class OfflineHarness {
  OfflineHarness(this.apiClient) : db = AppDatabase(NativeDatabase.memory()) {
    cache = ResourceCache(db);
    coordinator = SyncCoordinator(database: db, apiClient: apiClient);
  }

  final ApiClient apiClient;
  final AppDatabase db;
  late final ResourceCache cache;
  late final SyncCoordinator coordinator;

  List<Override> get overrides => [
    apiClientProvider.overrideWithValue(apiClient),
    syncCoordinatorProvider.overrideWithValue(coordinator),
    resourceCacheProvider.overrideWithValue(cache),
  ];

  Future<List<SyncOperation>> ops() => db.select(db.syncOperations).get();

  Future<void> dispose() async {
    coordinator.stop();
    await db.close();
  }
}
