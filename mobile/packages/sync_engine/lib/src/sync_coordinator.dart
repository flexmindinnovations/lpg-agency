// `SyncCoordinator`'s constructor takes `apiClient` (public) and assigns it
// to `_apiClient` (private) — an initializing formal can't do that because
// its named-parameter label is the field name itself, and every real
// caller of this constructor lives outside this library.
// ignore_for_file: prefer_initializing_formals

import 'dart:async';
import 'dart:convert';

import 'package:api_client/api_client.dart';
import 'package:dio/dio.dart';
import 'package:drift/drift.dart' as drift;
import 'package:local_storage/local_storage.dart';
import 'package:uuid/uuid.dart';

/// Coordinator that handles offline-first synchronization with the backend API.
class SyncCoordinator {
  SyncCoordinator({required AppDatabase database, required ApiClient apiClient})
    : _db = database,
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
    await _db
        .into(_db.syncOperations)
        .insert(
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
      final pendingOps =
          await (_db.select(_db.syncOperations)
                ..where(
                  (t) => t.status.equals('pending') | t.status.equals('error'),
                )
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

      await _dispatch(op);

      // Mark as synced on success
      await (_db.update(_db.syncOperations)..where((t) => t.id.equals(op.id)))
          .write(const SyncOperationsCompanion(status: drift.Value('synced')));
    } on DioException catch (e) {
      if (e.response?.statusCode == 409) {
        // Optimistic concurrency conflict - mark for manual review
        await (_db.update(
          _db.syncOperations,
        )..where((t) => t.id.equals(op.id))).write(
          SyncOperationsCompanion(
            status: const drift.Value('conflict'),
            errorMessage: drift.Value(e.message ?? 'Conflict occurred'),
          ),
        );
      } else {
        // Network or other error - mark as error to retry later
        await (_db.update(
          _db.syncOperations,
        )..where((t) => t.id.equals(op.id))).write(
          SyncOperationsCompanion(
            status: const drift.Value('error'),
            errorMessage: drift.Value(e.message ?? 'Unknown error'),
          ),
        );
      }
    } catch (e) {
      await (_db.update(
        _db.syncOperations,
      )..where((t) => t.id.equals(op.id))).write(
        SyncOperationsCompanion(
          status: const drift.Value('error'),
          errorMessage: drift.Value(e.toString()),
        ),
      );
    }
  }

  /// Routes a queued operation to its real backend endpoint by `op.type`.
  ///
  /// Each case hits `_apiClient.dio` directly rather than going through the
  /// matching `api_client` wrapper class (e.g. `OrderApi.createOrder`) even
  /// though that class exists and builds the identical request — those
  /// wrappers return a `Result`, swallowing `DioException` (including the
  /// HTTP status code) into a plain `Failure`. `_processOperation`'s
  /// catch blocks above need the real exception to tell a 409 conflict
  /// apart from a retryable network error, so the request is built here
  /// with the same shape instead.
  ///
  /// `op.idempotencyKey` (persisted per queued operation, unique in
  /// `SyncOperations`) is reused as the `Idempotency-Key` header — a retry
  /// after a dropped connection must replay the *same* key, or the backend
  /// sees it as a brand new booking rather than a resend of this one.
  Future<void> _dispatch(SyncOperation op) async {
    final headers = {'Idempotency-Key': op.idempotencyKey};

    switch (op.type) {
      case 'delivery_confirmation':
        // Driver App's proof-of-delivery flow. `/deliveries/sync` is not a
        // real backend route either (out of scope for this fix — tracked
        // separately from the Customer App order-placement bug this
        // dispatch was rewritten for); left exactly as it was.
        await _apiClient.dio.post(
          '/deliveries/sync',
          data: op.payload,
          options: Options(headers: headers),
        );
      case 'order_gas':
        // Payload is a `CreateOrderRequest.toJson()` body — Customer App's
        // order-placement flow (`order_bottom_sheet.dart`). Previously this
        // fell through to a nonexistent `POST /sync/order_gas` (confirmed
        // 404 live); this is the real endpoint `OrderApi.createOrder`
        // itself calls.
        await _apiClient.dio.post(
          '/api/v1/orders',
          data: jsonDecode(op.payload),
          options: Options(headers: headers),
        );
      default:
        throw StateError(
          'SyncCoordinator has no route for operation type "${op.type}".',
        );
    }
  }
}
