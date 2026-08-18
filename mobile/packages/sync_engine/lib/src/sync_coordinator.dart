import 'dart:async';
import 'package:api_client/api_client.dart';
import 'package:dio/dio.dart';
import 'package:drift/drift.dart' as drift;
import 'package:local_storage/local_storage.dart';
import 'package:uuid/uuid.dart';

/// Coordinator that handles offline-first synchronization with the backend API.
class SyncCoordinator {
  SyncCoordinator({
    required AppDatabase database,
    required ApiClient apiClient,
  })  : _db = database,
        _apiClient = apiClient;

  final AppDatabase _db;
  final ApiClient _apiClient;
  bool _isSyncing = false;
  Timer? _syncTimer;

  /// Starts the background sync loop.
  void start() {
    _syncTimer?.cancel();
    // Poll every 10 seconds for simplicity. In production, this should also
    // trigger on connectivity restoration events via connectivity_plus.
    _syncTimer = Timer.periodic(const Duration(seconds: 10), (_) => syncNow());
  }

  /// Stops the background sync loop.
  void stop() {
    _syncTimer?.cancel();
    _syncTimer = null;
  }

  /// Enqueues a new sync operation and immediately attempts to sync.
  Future<void> enqueueOperation(String type, String payload) async {
    final uuid = const Uuid().v4();
    await _db.into(_db.syncOperations).insert(
          SyncOperationsCompanion.insert(
            id: uuid,
            type: type,
            payload: payload,
            idempotencyKey: uuid,
          ),
        );
    syncNow();
  }

  /// Manually triggers a synchronization of all pending operations.
  Future<void> syncNow() async {
    if (_isSyncing) return;
    _isSyncing = true;

    try {
      final pendingOps = await (_db.select(_db.syncOperations)
            ..where((t) => t.status.equals('pending') | t.status.equals('error'))
            ..orderBy([(t) => drift.OrderingTerm.asc(t.createdAt)]))
          .get();

      for (final op in pendingOps) {
        await _processOperation(op);
      }
    } finally {
      _isSyncing = false;
    }
  }

  Future<void> _processOperation(SyncOperation op) async {
    try {
      // Mark as syncing
      await (_db.update(_db.syncOperations)..where((t) => t.id.equals(op.id)))
          .write(const SyncOperationsCompanion(status: drift.Value('syncing')));

      // In a real app, you'd route this by `op.type`. We use a generic POST
      // to the backend for this example, with the idempotency key in headers.
      // E.g., if type == 'delivery_confirmation', call DeliveryApi.
      // Since this is generic, we just catch the exceptions for tests.
      
      final headers = {'Idempotency-Key': op.idempotencyKey};
      
      if (op.type == 'delivery_confirmation') {
        await _apiClient.dio.post('/deliveries/sync', data: op.payload, options: Options(headers: headers));
      } else {
        // generic fallback for tests
        await _apiClient.dio.post('/sync/${op.type}', data: op.payload, options: Options(headers: headers));
      }

      // Mark as synced on success
      await (_db.update(_db.syncOperations)..where((t) => t.id.equals(op.id)))
          .write(const SyncOperationsCompanion(status: drift.Value('synced')));
          
    } on DioException catch (e) {
      if (e.response?.statusCode == 409) {
        // Optimistic concurrency conflict - mark for manual review
        await (_db.update(_db.syncOperations)..where((t) => t.id.equals(op.id)))
            .write(SyncOperationsCompanion(
              status: const drift.Value('conflict'),
              errorMessage: drift.Value(e.message ?? 'Conflict occurred'),
            ));
      } else {
        // Network or other error - mark as error to retry later
        await (_db.update(_db.syncOperations)..where((t) => t.id.equals(op.id)))
            .write(SyncOperationsCompanion(
              status: const drift.Value('error'),
              errorMessage: drift.Value(e.message ?? 'Unknown error'),
            ));
      }
    } catch (e) {
      await (_db.update(_db.syncOperations)..where((t) => t.id.equals(op.id)))
          .write(SyncOperationsCompanion(
            status: const drift.Value('error'),
            errorMessage: drift.Value(e.toString()),
          ));
    }
  }
}
