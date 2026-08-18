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

  @override
  Future<ResponseBody> fetch(RequestOptions options, Stream<List<int>>? requestStream, Future<void>? cancelFuture) async {
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
    
    await coordinator.enqueueOperation('delivery_confirmation', '{"data": "test"}');

    // Wait a brief moment for the async syncNow to complete
    await Future.delayed(const Duration(milliseconds: 100));

    final ops = await db.select(db.syncOperations).get();
    expect(ops.length, 1);
    expect(ops.first.type, 'delivery_confirmation');
    expect(ops.first.status, 'synced');
  });

  test('SyncCoordinator marks as conflict on 409', () async {
    fakeAdapter.responseStatus = 409;
    
    await coordinator.enqueueOperation('delivery_confirmation', '{"data": "test"}');

    // Wait a brief moment for the async syncNow to complete
    await Future.delayed(const Duration(milliseconds: 100));

    final ops = await db.select(db.syncOperations).get();
    expect(ops.length, 1);
    expect(ops.first.status, 'conflict');
  });
  
  test('SyncCoordinator marks as error on 500', () async {
    fakeAdapter.responseStatus = 500;
    
    await coordinator.enqueueOperation('delivery_confirmation', '{"data": "test"}');

    // Wait a brief moment for the async syncNow to complete
    await Future.delayed(const Duration(milliseconds: 100));

    final ops = await db.select(db.syncOperations).get();
    expect(ops.length, 1);
    expect(ops.first.status, 'error');
  });
}
