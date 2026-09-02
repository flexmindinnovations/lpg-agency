import 'dart:async';
import 'dart:convert';

import 'package:api_client/api_client.dart';
import 'package:dio/dio.dart';
import 'package:drift/native.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:local_storage/local_storage.dart';
import 'package:sync_engine/sync_engine.dart';

class FakeAdapter implements HttpClientAdapter {
  int responseStatus = 200;
  String responseData = '{}';
  final List<RequestOptions> requests = [];

  RequestOptions? get lastRequest => requests.isEmpty ? null : requests.last;

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<List<int>>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    requests.add(options);
    return ResponseBody.fromString(
      responseData,
      responseStatus,
      headers: {
        Headers.contentTypeHeader: [Headers.jsonContentType],
      },
    );
  }

  @override
  void close({bool force = false}) {}
}

class FakeConnectivityMonitor implements ConnectivityMonitor {
  final _controller = StreamController<bool>.broadcast();

  void emit(bool online) => _controller.add(online);

  @override
  Stream<bool> get onConnectivityChanged => _controller.stream;

  Future<void> dispose() => _controller.close();
}

String _departPayload(String orderId) => jsonEncode({
  'path': '/api/v1/orders/$orderId/depart',
  'body': null,
});

void main() {
  late AppDatabase db;
  late ApiClient apiClient;
  late SyncCoordinator coordinator;
  late FakeAdapter fakeAdapter;

  setUp(() {
    db = AppDatabase(NativeDatabase.memory());
    fakeAdapter = FakeAdapter();
    apiClient = ApiClient(baseUrl: 'http://localhost');
    apiClient.dio.httpClientAdapter = fakeAdapter;
    coordinator = SyncCoordinator(database: db, apiClient: apiClient);
  });

  tearDown(() async {
    coordinator.stop();
    await db.close();
  });

  Future<void> settle() =>
      Future<void>.delayed(const Duration(milliseconds: 100));

  Future<SyncOperation> onlyOp() async =>
      (await db.select(db.syncOperations).get()).single;

  test('a driver op syncs to the structured path with the idempotency key',
      () async {
    fakeAdapter.responseStatus = 200;

    await coordinator.enqueueOperation('order_depart', _departPayload('order-1'));
    await settle();

    expect(fakeAdapter.lastRequest?.path, '/api/v1/orders/order-1/depart');
    expect(fakeAdapter.lastRequest?.headers['Idempotency-Key'], isNotNull);
    expect((await onlyOp()).status, 'synced');
  });

  test('the same idempotency key is sent on every attempt', () async {
    fakeAdapter.responseStatus = 500;
    await coordinator.enqueueOperation('order_depart', _departPayload('order-1'));
    await settle();

    fakeAdapter.responseStatus = 200;
    await coordinator.retryOperation((await onlyOp()).id);
    await settle();

    final keys = fakeAdapter.requests
        .map((r) => r.headers['Idempotency-Key'])
        .toSet();
    expect(keys, hasLength(1));
    expect((await onlyOp()).status, 'synced');
  });

  test('order_gas still routes to POST /api/v1/orders', () async {
    fakeAdapter.responseStatus = 201;
    await coordinator.enqueueOperation(
      'order_gas',
      jsonEncode({
        'customer_id': 'c1',
        'lines': [
          {'cylinder_type_id': 'cyl', 'quantity': 1},
        ],
      }),
    );
    await settle();

    expect(fakeAdapter.lastRequest?.path, '/api/v1/orders');
    expect((await onlyOp()).status, 'synced');
  });

  test('a 409 stale transition is marked conflict', () async {
    fakeAdapter
      ..responseStatus = 409
      ..responseData = '{"error_code": "CONFLICT"}';

    await coordinator.enqueueOperation('order_depart', _departPayload('order-1'));
    await settle();

    expect((await onlyOp()).status, 'conflict');
  });

  test('a 409 IDEMPOTENCY_KEY_CONFLICT is marked failed, not conflict',
      () async {
    fakeAdapter
      ..responseStatus = 409
      ..responseData = '{"error_code": "IDEMPOTENCY_KEY_CONFLICT"}';

    await coordinator.enqueueOperation('order_depart', _departPayload('order-1'));
    await settle();

    final op = await onlyOp();
    expect(op.status, 'failed');
    expect(op.errorMessage, contains('Idempotency key'));
  });

  test('a permanent 4xx (422) is marked failed immediately', () async {
    fakeAdapter
      ..responseStatus = 422
      ..responseData = '{"error_code": "VALIDATION_FAILED"}';

    await coordinator.enqueueOperation('order_depart', _departPayload('order-1'));
    await settle();

    final op = await onlyOp();
    expect(op.status, 'failed');
    expect(op.retryCount, 0);
  });

  test('a 500 increments retryCount and stays retryable', () async {
    fakeAdapter.responseStatus = 500;

    await coordinator.enqueueOperation('order_depart', _departPayload('order-1'));
    await settle();

    final op = await onlyOp();
    expect(op.status, 'error');
    expect(op.retryCount, 1);
    expect(op.lastAttemptAt, isNotNull);
  });

  test('a 500 becomes failed once retries are exhausted', () async {
    coordinator = SyncCoordinator(
      database: db,
      apiClient: apiClient,
      maxRetries: 1,
    );
    fakeAdapter.responseStatus = 500;

    await coordinator.enqueueOperation('order_depart', _departPayload('order-1'));
    await settle();

    expect((await onlyOp()).status, 'failed');
  });

  test('an errored op inside its backoff window is skipped by syncNow',
      () async {
    fakeAdapter.responseStatus = 500;
    await coordinator.enqueueOperation('order_depart', _departPayload('order-1'));
    await settle();
    expect(fakeAdapter.requests, hasLength(1));

    // Immediately re-drain: the op is backing off (5s for retry #1), so no
    // second HTTP call and retryCount is untouched.
    await coordinator.syncNow();
    await settle();
    expect(fakeAdapter.requests, hasLength(1));
    expect((await onlyOp()).retryCount, 1);
  });

  test('an unrecognized op type is marked failed with its type in the message',
      () async {
    await coordinator.enqueueOperation('some_future_op', '{}');
    await settle();

    final op = await onlyOp();
    expect(op.status, 'failed');
    expect(op.errorMessage, contains('some_future_op'));
  });

  test('regained connectivity drains the queue', () async {
    final connectivity = FakeConnectivityMonitor();
    addTearDown(connectivity.dispose);
    coordinator = SyncCoordinator(
      database: db,
      apiClient: apiClient,
      connectivity: connectivity,
      pollInterval: const Duration(hours: 1),
    );

    fakeAdapter.responseStatus = 500;
    await coordinator.enqueueOperation('order_depart', _departPayload('order-1'));
    await settle();
    expect((await onlyOp()).status, 'error');

    coordinator.start();
    fakeAdapter.responseStatus = 200;
    connectivity.emit(true);
    await settle();

    expect((await onlyOp()).status, 'synced');
  });

  test('watchPendingCount / watchIssues / discardOperation', () async {
    fakeAdapter
      ..responseStatus = 409
      ..responseData = '{"error_code": "CONFLICT"}';
    await coordinator.enqueueOperation('order_depart', _departPayload('a'));
    await settle();

    fakeAdapter.responseStatus = 500;
    await coordinator.enqueueOperation('order_depart', _departPayload('b'));
    await settle();

    expect(await coordinator.watchPendingCount().first, 1); // just the errored one
    final issues = await coordinator.watchIssues().first;
    expect(issues.map((o) => o.status), contains('conflict'));

    await coordinator.discardOperation(issues.first.id);
    expect((await coordinator.watchIssues().first), hasLength(0));
  });
}
