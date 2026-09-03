// `SyncCoordinator`'s constructor takes `apiClient` (public) and assigns it
// to `_apiClient` (private) — an initializing formal can't do that because
// its named-parameter label is the field name itself, and every real
// caller of this constructor lives outside this library.
// ignore_for_file: prefer_initializing_formals

import 'dart:async';
import 'dart:convert';
import 'dart:math' as math;

import 'package:api_client/api_client.dart';
import 'package:dio/dio.dart';
import 'package:drift/drift.dart' as drift;
import 'package:local_storage/local_storage.dart';
import 'package:uuid/uuid.dart';

import 'connectivity_monitor.dart';
import 'media_store.dart';

/// Statuses a [SyncOperation] can be `error`-retried from vs. the terminal
/// ones the driver has to look at.
const _retryableStatuses = ['pending', 'error'];

/// The driver-app mutation queue: every offline write is a durable, ordered
/// [SyncOperation] with a client-generated idempotency key, drained here
/// against the real backend when connectivity allows.
///
/// `_dispatch` hits `_apiClient.dio` directly rather than the `api_client`
/// wrapper classes: those return a `Result`, swallowing the `DioException`
/// (and its status code) into a plain `Failure`, and [_processOperation]
/// needs the real status to tell a 409 conflict from a retryable network
/// error.
class SyncCoordinator {
  SyncCoordinator({
    required AppDatabase database,
    required ApiClient apiClient,
    ConnectivityMonitor? connectivity,
    MediaStore? mediaStore,
    Duration pollInterval = const Duration(seconds: 30),
    int maxRetries = 8,
  }) : _db = database,
       _apiClient = apiClient,
       _connectivity = connectivity,
       _mediaStore = mediaStore,
       _pollInterval = pollInterval,
       _maxRetries = maxRetries;

  final AppDatabase _db;
  final ApiClient _apiClient;
  final ConnectivityMonitor? _connectivity;
  final MediaStore? _mediaStore;
  final Duration _pollInterval;
  final int _maxRetries;

  bool _isSyncing = false;
  Timer? _syncTimer;
  StreamSubscription<bool>? _connSub;

  /// Starts the background sync loop: a periodic poll (the fallback) plus an
  /// immediate drain whenever connectivity is regained (the common case).
  void start() {
    _syncTimer?.cancel();
    _syncTimer = Timer.periodic(_pollInterval, (_) => syncNow());

    _connSub?.cancel();
    _connSub = _connectivity?.onConnectivityChanged.listen((online) {
      // A connectivity transition is fresh evidence the network is back, so
      // drain everything now rather than waiting out each op's backoff.
      if (online) syncNow(ignoreBackoff: true);
    });
  }

  /// Stops the background sync loop.
  void stop() {
    _syncTimer?.cancel();
    _syncTimer = null;
    _connSub?.cancel();
    _connSub = null;
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

  /// Manually triggers a synchronization of all pending operations, oldest
  /// first (which preserves per-aggregate ordering). Ops in an `error` state
  /// whose backoff window hasn't elapsed are skipped this pass unless
  /// [ignoreBackoff] is set (a connectivity-regained drain).
  Future<void> syncNow({bool ignoreBackoff = false}) async {
    if (_isSyncing) return;
    _isSyncing = true;

    try {
      final ops =
          await (_db.select(_db.syncOperations)
                ..where((t) => t.status.isIn(_retryableStatuses))
                ..orderBy([(t) => drift.OrderingTerm.asc(t.createdAt)]))
              .get();

      final now = DateTime.now();
      for (final op in ops) {
        if (!ignoreBackoff && _isBackingOff(op, now)) continue;
        await _processOperation(op);
      }
    } finally {
      _isSyncing = false;
    }
  }

  /// A `Stream` of the count of operations still working through the queue
  /// (`pending` / `error` / `syncing`) — drives the shell's sync badge.
  Stream<int> watchPendingCount() {
    final count = _db.syncOperations.id.count();
    final query = _db.selectOnly(_db.syncOperations)
      ..addColumns([count])
      ..where(
        _db.syncOperations.status.isIn(['pending', 'error', 'syncing']),
      );
    return query.map((row) => row.read(count) ?? 0).watchSingle();
  }

  /// A `Stream` of the operations still in flight (`pending` / `error` /
  /// `syncing`), oldest first — the app derives its optimistic-overlay set
  /// (which orders/routes have an unsynced mutation) from this.
  Stream<List<SyncOperation>> watchActive() {
    return (_db.select(_db.syncOperations)
          ..where((t) => t.status.isIn(['pending', 'error', 'syncing']))
          ..orderBy([(t) => drift.OrderingTerm.asc(t.createdAt)]))
        .watch();
  }

  /// A `Stream` of the operations that need the driver's attention —
  /// `failed` (retries exhausted or a permanent 4xx) and `conflict` (the
  /// server rejected a stale transition). Newest first.
  Stream<List<SyncOperation>> watchIssues() {
    return (_db.select(_db.syncOperations)
          ..where((t) => t.status.isIn(['failed', 'conflict']))
          ..orderBy([(t) => drift.OrderingTerm.desc(t.createdAt)]))
        .watch();
  }

  /// Puts a `failed` operation back in the queue (the driver tapped
  /// "retry"), clearing its attempt history.
  Future<void> retryOperation(String id) async {
    await (_db.update(_db.syncOperations)..where((t) => t.id.equals(id))).write(
      const SyncOperationsCompanion(
        status: drift.Value('pending'),
        retryCount: drift.Value(0),
        errorMessage: drift.Value(null),
      ),
    );
    syncNow();
  }

  /// Drops an operation from the queue (the driver acknowledged a `conflict`
  /// or gave up on a `failed` one). The server is authoritative, so the
  /// local optimistic state is reconciled separately by invalidating the
  /// affected read providers.
  Future<void> discardOperation(String id) async {
    await (_db.delete(_db.syncOperations)..where((t) => t.id.equals(id))).go();
  }

  bool _isBackingOff(SyncOperation op, DateTime now) {
    if (op.status != 'error' || op.lastAttemptAt == null) return false;
    return now.isBefore(op.lastAttemptAt!.add(_backoff(op.retryCount)));
  }

  /// Capped exponential backoff: 5s, 10s, 20s, … up to 10 minutes.
  Duration _backoff(int retryCount) {
    final seconds = math.min(600, 5 * math.pow(2, math.max(0, retryCount - 1)));
    return Duration(seconds: seconds.toInt());
  }

  Future<void> _processOperation(SyncOperation op) async {
    await _write(
      op.id,
      const SyncOperationsCompanion(status: drift.Value('syncing')),
    );

    try {
      await _dispatch(op);
      await _write(
        op.id,
        SyncOperationsCompanion(
          status: const drift.Value('synced'),
          lastAttemptAt: drift.Value(DateTime.now()),
        ),
      );
    } on DioException catch (e) {
      await _handleDioFailure(op, e);
    } catch (e) {
      // A non-HTTP failure — an unknown op type, a malformed payload. It
      // will never succeed on replay, so surface it rather than retry.
      await _write(
        op.id,
        SyncOperationsCompanion(
          status: const drift.Value('failed'),
          errorMessage: drift.Value(e.toString()),
          lastAttemptAt: drift.Value(DateTime.now()),
        ),
      );
    }
  }

  Future<void> _handleDioFailure(SyncOperation op, DioException e) async {
    final status = e.response?.statusCode;
    final code = _errorCode(e.response?.data);

    if (status == 409 && code == 'IDEMPOTENCY_KEY_CONFLICT') {
      // The same key was replayed with a different body — a client bug, not
      // a network retry. Nothing to do but surface it.
      await _write(
        op.id,
        SyncOperationsCompanion(
          status: const drift.Value('failed'),
          errorMessage: const drift.Value(
            'Idempotency key reused with a different request.',
          ),
          lastAttemptAt: drift.Value(DateTime.now()),
        ),
      );
      return;
    }

    if (status == 409) {
      // A genuinely stale transition — another device or the office already
      // moved this aggregate. The server is authoritative; the driver
      // acknowledges and discards.
      await _write(
        op.id,
        SyncOperationsCompanion(
          status: const drift.Value('conflict'),
          errorMessage: drift.Value(e.response?.data.toString() ?? e.message),
          lastAttemptAt: drift.Value(DateTime.now()),
        ),
      );
      return;
    }

    if (status != null && status >= 400 && status < 500) {
      // A permanent bad request (422 validation, 404, …) — replaying the
      // identical payload will keep failing.
      await _write(
        op.id,
        SyncOperationsCompanion(
          status: const drift.Value('failed'),
          errorMessage: drift.Value('HTTP $status: ${e.message}'),
          lastAttemptAt: drift.Value(DateTime.now()),
        ),
      );
      return;
    }

    // Network error, timeout or 5xx — retryable. Back off, or give up once
    // the attempts are exhausted.
    final attempts = op.retryCount + 1;
    await _write(
      op.id,
      SyncOperationsCompanion(
        status: drift.Value(attempts >= _maxRetries ? 'failed' : 'error'),
        retryCount: drift.Value(attempts),
        errorMessage: drift.Value(e.message ?? 'Network error'),
        lastAttemptAt: drift.Value(DateTime.now()),
      ),
    );
  }

  Future<void> _write(String id, SyncOperationsCompanion values) async {
    await (_db.update(_db.syncOperations)..where((t) => t.id.equals(id))).write(
      values,
    );
  }

  static String? _errorCode(Object? data) {
    if (data is Map && data['error_code'] is String) {
      return data['error_code'] as String;
    }
    return null;
  }

  /// Routes a queued operation to its real backend endpoint by `op.type`.
  ///
  /// `op.idempotencyKey` (persisted per queued operation, unique in
  /// `SyncOperations`) is sent as the `Idempotency-Key` header — a retry
  /// after a dropped connection must replay the *same* key, or the backend
  /// applies it twice.
  ///
  /// Most driver ops carry a `{"path", "body"}` payload so this method stays
  /// a thin router; the payload is built app-side next to the screen that
  /// knows the real request shape. `order_deliver` is the exception — it
  /// carries local media that has to be uploaded first ([_dispatchDeliver]).
  Future<void> _dispatch(SyncOperation op) async {
    final options = Options(headers: {'Idempotency-Key': op.idempotencyKey});

    switch (op.type) {
      case 'order_gas':
        // Customer App order placement — payload is a `CreateOrderRequest`
        // body, posted to the same endpoint `OrderApi.createOrder` uses.
        await _apiClient.dio.post(
          '/api/v1/orders',
          data: jsonDecode(op.payload),
          options: options,
        );
      case 'order_deliver':
        await _dispatchDeliver(op, options);
      case 'order_depart':
      case 'order_failed_delivery':
      case 'order_reschedule':
      case 'cash_handover_declare':
      case 'route_confirm_load':
        final decoded = jsonDecode(op.payload) as Map<String, dynamic>;
        await _apiClient.dio.post(
          decoded['path'] as String,
          data: decoded['body'],
          options: options,
        );
      default:
        throw StateError(
          'SyncCoordinator has no route for operation type "${op.type}".',
        );
    }
  }

  /// Proof-of-delivery sync, in order and resumable:
  /// 1. for each media entry without a `blobRef`, upload the local file and
  ///    write the returned `blob_ref` **back onto the op's payload** — a
  ///    mid-sequence failure then resumes from the next file, not the first;
  /// 2. `POST .../deliver` with the collected refs folded into
  ///    `proof_of_delivery` (same `Idempotency-Key`);
  /// 3. on success, delete the local media.
  ///
  /// `media` entries: `{field, key, filename, contentType, blobRef}` where
  /// `field` is `signature` / `photo` (→ `<field>_blob_ref`).
  Future<void> _dispatchDeliver(SyncOperation op, Options options) async {
    final store = _mediaStore;
    if (store == null) {
      throw StateError('order_deliver needs a MediaStore.');
    }

    final decoded = jsonDecode(op.payload) as Map<String, dynamic>;
    final media = (decoded['media'] as List).cast<Map<String, dynamic>>();

    for (final entry in media) {
      if (entry['blobRef'] != null) continue;
      final bytes = await store.read(entry['key'] as String);
      final form = FormData.fromMap({
        'file': MultipartFile.fromBytes(
          bytes,
          filename: entry['filename'] as String,
          contentType: DioMediaType.parse(entry['contentType'] as String),
        ),
      });
      final res = await _apiClient.dio.post<Map<String, dynamic>>(
        decoded['uploadPath'] as String,
        data: form,
        options: options,
      );
      entry['blobRef'] = res.data?['blob_ref'];
      // Persist after *each* upload — a failure on the next one then resumes
      // here, not from the first file.
      await _write(
        op.id,
        SyncOperationsCompanion(payload: drift.Value(jsonEncode(decoded))),
      );
    }

    final body = Map<String, dynamic>.from(decoded['body'] as Map);
    final pod = Map<String, dynamic>.from(body['proof_of_delivery'] as Map);
    for (final entry in media) {
      pod['${entry['field']}_blob_ref'] = entry['blobRef'];
    }
    body['proof_of_delivery'] = pod;

    await _apiClient.dio.post(
      decoded['path'] as String,
      data: body,
      options: options,
    );

    for (final entry in media) {
      await store.delete(entry['key'] as String);
    }
  }
}
