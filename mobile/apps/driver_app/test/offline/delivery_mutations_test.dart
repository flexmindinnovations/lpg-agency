import 'dart:convert';

import 'package:api_client/api_client.dart';
import 'package:dio/dio.dart';
import 'package:driver_app/src/offline/delivery_mutations.dart';
import 'package:drift/native.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:local_storage/local_storage.dart';
import 'package:sync_engine/sync_engine.dart';

/// Enqueue also kicks off a background `syncNow()`; a 200 keeps that path
/// short so it finishes before `tearDown` closes the database.
class _OkAdapter implements HttpClientAdapter {
  @override
  Future<ResponseBody> fetch(RequestOptions options, _, _) async =>
      ResponseBody.fromString(
        '{}',
        200,
        headers: {
          Headers.contentTypeHeader: [Headers.jsonContentType],
        },
      );

  @override
  void close({bool force = false}) {}
}

void main() {
  late AppDatabase db;
  late ResourceCache cache;
  late SyncCoordinator coordinator;
  late DeliveryMutations mutations;

  setUp(() {
    db = AppDatabase(NativeDatabase.memory());
    cache = ResourceCache(db);
    coordinator = SyncCoordinator(
      database: db,
      apiClient: ApiClient(baseUrl: 'http://x')
        ..dio.httpClientAdapter = _OkAdapter(),
    );
    mutations = DeliveryMutations(coordinator: coordinator, cache: cache);
  });

  tearDown(() async {
    coordinator.stop();
    // Let the background syncNow() from enqueue finish its DB writes.
    await Future<void>.delayed(const Duration(milliseconds: 50));
    await db.close();
  });

  test(
    'departStop moves the cached order optimistically and queues the op',
    () async {
      await cache.write('order', 'o1', {
        'id': 'o1',
        'status': 'ready_for_dispatch',
      });

      await mutations.departStop('o1');

      expect((await cache.read('order', 'o1'))!['status'], 'out_for_delivery');
      final op = (await db.select(db.syncOperations).get()).single;
      expect(op.type, 'order_depart');
      final payload = jsonDecode(op.payload) as Map<String, dynamic>;
      expect(payload['path'], '/api/v1/orders/o1/depart');
      expect(payload['aggregateId'], 'o1');
    },
  );

  test(
    'recordFailedDelivery carries the reason and resolution in the body',
    () async {
      await mutations.recordFailedDelivery(
        'o2',
        reasonCode: 'wrong_address',
        resolutionAction: 'reschedule',
      );

      final op = (await db.select(db.syncOperations).get()).single;
      expect(op.type, 'order_failed_delivery');
      final body = jsonDecode(op.payload)['body'] as Map<String, dynamic>;
      expect(body['reason_code'], 'wrong_address');
      expect(body['resolution_action'], 'reschedule');
    },
  );

  test(
    'declareCashHandover queues a cash_handover_declare op keyed by route',
    () async {
      await mutations.declareCashHandover(
        routeId: 'r1',
        driverId: 'd1',
        actualAmount: 1234.5,
      );

      final op = (await db.select(db.syncOperations).get()).single;
      expect(op.type, 'cash_handover_declare');
      final payload = jsonDecode(op.payload) as Map<String, dynamic>;
      expect(payload['aggregateId'], 'r1');
      expect((payload['body'] as Map)['actual_amount'], '1234.50');
    },
  );

  test(
    'a queued op with no cached order still enqueues (no optimistic write)',
    () async {
      await mutations.departStop('missing');

      expect(await cache.read('order', 'missing'), isNull);
      expect((await db.select(db.syncOperations).get()), hasLength(1));
    },
  );
}
