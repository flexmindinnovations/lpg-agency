import 'dart:typed_data';

import 'package:api_client/api_client.dart';
import 'package:driver_app/src/api_provider.dart';
import 'package:driver_app/src/offline/cached_resource.dart';
import 'package:driver_app/src/offline/connectivity.dart';
import 'package:driver_app/src/offline/media_store_provider.dart';
import 'package:driver_app/src/offline/sync_providers.dart';
import 'package:drift/native.dart';
import 'package:flutter_riverpod/misc.dart' show Override;
import 'package:local_storage/local_storage.dart';
import 'package:sync_engine/sync_engine.dart';

/// A [MediaStore] that keeps bytes in a map — no filesystem in tests.
class InMemoryMediaStore implements MediaStore {
  final _files = <String, Uint8List>{};

  Set<String> get keys => _files.keys.toSet();

  @override
  Future<void> write(String key, List<int> bytes) async {
    _files[key] = Uint8List.fromList(bytes);
  }

  @override
  Future<Uint8List> read(String key) async {
    final bytes = _files[key];
    if (bytes == null) throw StateError('no media at $key');
    return bytes;
  }

  @override
  Future<void> delete(String key) async => _files.remove(key);

  @override
  Future<bool> exists(String key) async => _files.containsKey(key);
}

class FakeConnectivityMonitor implements ConnectivityMonitor {
  FakeConnectivityMonitor({this.online = true});

  bool online;

  @override
  Future<bool> get isOnline async => online;

  @override
  Stream<bool> get onConnectivityChanged => const Stream.empty();
}

/// A real in-memory `SyncCoordinator` + `ResourceCache` + `MediaStore` for
/// tests that exercise the offline write path (Stage 4+). `apiClient` should
/// carry a fake `HttpClientAdapter` so enqueued ops sync against a stub.
class OfflineHarness {
  OfflineHarness(this.apiClient, {bool online = true})
    : db = AppDatabase(NativeDatabase.memory()),
      connectivity = FakeConnectivityMonitor(online: online) {
    cache = ResourceCache(db);
    media = InMemoryMediaStore();
    coordinator = SyncCoordinator(
      database: db,
      apiClient: apiClient,
      mediaStore: media,
    );
  }

  final ApiClient apiClient;
  final AppDatabase db;
  final FakeConnectivityMonitor connectivity;
  late final ResourceCache cache;
  late final InMemoryMediaStore media;
  late final SyncCoordinator coordinator;

  List<Override> get overrides => [
    apiClientProvider.overrideWithValue(apiClient),
    syncCoordinatorProvider.overrideWithValue(coordinator),
    resourceCacheProvider.overrideWithValue(cache),
    mediaStoreProvider.overrideWithValue(media),
    connectivityMonitorProvider.overrideWithValue(connectivity),
  ];

  Future<List<SyncOperation>> ops() => db.select(db.syncOperations).get();

  Future<void> dispose() async {
    coordinator.stop();
    await Future<void>.delayed(const Duration(milliseconds: 50));
    await db.close();
  }
}
