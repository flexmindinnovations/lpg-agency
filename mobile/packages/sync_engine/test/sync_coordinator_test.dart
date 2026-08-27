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
  RequestOptions? lastRequest;

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<List<int>>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    lastRequest = options;
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

void main() {
  late AppDatabase db;
  late ApiClient apiClient;
  late SyncCoordinator coordinator;
  late FakeAdapter fakeAdapter;

  setUp(() {
    db = AppDatabase(NativeDatabase.memory());
    fakeAdapter = FakeAdapter();

    // We create a generic ApiClient and replace its adapter.
    apiClient = ApiClient(baseUrl: 'http://localhost');
    apiClient.dio.httpClientAdapter = fakeAdapter;

    coordinator = SyncCoordinator(database: db, apiClient: apiClient);
  });

  tearDown(() async {
    coordinator.stop();
    await db.close();
  });

  test('SyncCoordinator enqueues and syncs operation successfully', () async {
    fakeAdapter.responseStatus = 200;

    await coordinator.enqueueOperation(
      'delivery_confirmation',
      '{"data": "test"}',
    );

    // Wait a brief moment for the async syncNow to complete
    await Future.delayed(const Duration(milliseconds: 100));

    final ops = await db.select(db.syncOperations).get();
    expect(ops.length, 1);
    expect(ops.first.type, 'delivery_confirmation');
    expect(ops.first.status, 'synced');
  });

  test('SyncCoordinator marks as conflict on 409', () async {
    fakeAdapter.responseStatus = 409;

    await coordinator.enqueueOperation(
      'delivery_confirmation',
      '{"data": "test"}',
    );

    // Wait a brief moment for the async syncNow to complete
    await Future.delayed(const Duration(milliseconds: 100));

    final ops = await db.select(db.syncOperations).get();
    expect(ops.length, 1);
    expect(ops.first.status, 'conflict');
  });

  test('SyncCoordinator marks as error on 500', () async {
    fakeAdapter.responseStatus = 500;

    await coordinator.enqueueOperation(
      'delivery_confirmation',
      '{"data": "test"}',
    );

    // Wait a brief moment for the async syncNow to complete
    await Future.delayed(const Duration(milliseconds: 100));

    final ops = await db.select(db.syncOperations).get();
    expect(ops.length, 1);
    expect(ops.first.status, 'error');
  });

  test(
    'SyncCoordinator routes order_gas to POST /api/v1/orders with the '
    'stored idempotency key, not the dead /sync/order_gas fallback',
    () async {
      fakeAdapter.responseStatus = 201;

      final payload = jsonEncode({
        'branch_id': 'branch-1',
        'customer_id': 'customer-1',
        'address_id': 'address-1',
        'delivery_address': {'address_line': '221B Baker Street'},
        'booking_source': 'app',
        'requested_date': '2026-09-01T00:00:00Z',
        'lines': [
          {'cylinder_type_id': 'cyl-14kg', 'quantity': 1},
        ],
      });
      await coordinator.enqueueOperation('order_gas', payload);

      await Future.delayed(const Duration(milliseconds: 100));

      expect(fakeAdapter.lastRequest?.path, '/api/v1/orders');
      expect(fakeAdapter.lastRequest?.headers['Idempotency-Key'], isNotNull);

      final ops = await db.select(db.syncOperations).get();
      expect(ops.single.status, 'synced');
    },
  );

  test('SyncCoordinator marks an unrecognized operation type as error rather '
      'than silently POSTing to a made-up endpoint', () async {
    await coordinator.enqueueOperation('some_future_op_type', '{}');

    await Future.delayed(const Duration(milliseconds: 100));

    final ops = await db.select(db.syncOperations).get();
    expect(ops.single.status, 'error');
    expect(ops.single.errorMessage, contains('some_future_op_type'));
  });
}
