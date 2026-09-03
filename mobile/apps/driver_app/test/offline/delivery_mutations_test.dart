import 'dart:convert';

import 'package:api_client/api_client.dart';
import 'package:dio/dio.dart';
import 'package:driver_app/src/offline/delivery_mutations.dart';
import 'package:drift/native.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:local_storage/local_storage.dart';
import 'package:sync_engine/sync_engine.dart';

import '../support/offline_harness.dart';

/// Serves the POD upload + deliver endpoints. `deliverStatus` lets a test
/// simulate a rejected OTP.
class _DeliverAdapter implements HttpClientAdapter {
  int deliverStatus = 200;
  bool offline = false;
  final List<String> paths = [];

  @override
  Future<ResponseBody> fetch(RequestOptions options, _, _) async {
    if (offline) {
      throw DioException.connectionError(
        requestOptions: options,
        reason: 'offline',
      );
    }
    paths.add(options.path);
    if (options.path.endsWith('/pod-attachments')) {
      return _json({'blob_ref': 'blob-${paths.length}'}, 201);
    }
    if (options.path.endsWith('/deliver')) {
      return _json(
        deliverStatus == 200
            ? {'order': _minimalOrder}
            : {'error_code': 'OTP_MISMATCH', 'detail': 'Wrong code.'},
        deliverStatus,
      );
    }
    return _json({}, 200);
  }

  @override
  void close({bool force = false}) {}
}

const _minimalOrder = {
  'id': 'o4',
  'tenant_id': 't1',
  'branch_id': 'b1',
  'customer_id': 'c1',
  'address_id': 'a1',
  'delivery_address': {'address_line': '1 Test St'},
  'status': 'delivered',
  'booking_source': 'mobile_app',
  'requested_date': '2026-09-01T00:00:00Z',
  'metadata': <String, dynamic>{},
  'lines': <dynamic>[],
};

ResponseBody _json(Object body, int status) => ResponseBody.fromString(
  jsonEncode(body),
  status,
  headers: {
    Headers.contentTypeHeader: [Headers.jsonContentType],
  },
);

const _lines = [
  DeliveredLineRequest(
    cylinderTypeId: 'ct1',
    quantityDelivered: 1,
    quantityCollectedEmpty: 1,
  ),
];

void main() {
  late AppDatabase db;
  late ResourceCache cache;
  late InMemoryMediaStore media;
  late _DeliverAdapter adapter;
  late SyncCoordinator coordinator;
  late ApiClient client;

  setUp(() {
    db = AppDatabase(NativeDatabase.memory());
    cache = ResourceCache(db);
    media = InMemoryMediaStore();
    adapter = _DeliverAdapter();
    client = ApiClient(baseUrl: 'http://x')..dio.httpClientAdapter = adapter;
    coordinator = SyncCoordinator(
      database: db,
      apiClient: client,
      mediaStore: media,
    );
  });

  tearDown(() async {
    coordinator.stop();
    await Future<void>.delayed(const Duration(milliseconds: 50));
    await db.close();
  });

  DeliveryMutations build({required bool online}) => DeliveryMutations(
    coordinator: coordinator,
    cache: cache,
    orderApi: OrderApi(client.dio),
    connectivity: FakeConnectivityMonitor(online: online),
    mediaStore: media,
  );

  Future<SyncOperation?> onlyOpOrNull() async {
    final ops = await db.select(db.syncOperations).get();
    return ops.isEmpty ? null : ops.single;
  }

  test(
    'departStop moves the cached order optimistically and queues the op',
    () async {
      await cache.write('order', 'o1', {
        'id': 'o1',
        'status': 'ready_for_dispatch',
      });

      await build(online: true).departStop('o1');

      expect((await cache.read('order', 'o1'))!['status'], 'out_for_delivery');
      final op = (await onlyOpOrNull())!;
      expect(op.type, 'order_depart');
      expect(jsonDecode(op.payload)['path'], '/api/v1/orders/o1/depart');
      expect(jsonDecode(op.payload)['aggregateId'], 'o1');
    },
  );

  test(
    'recordFailedDelivery carries the reason and resolution in the body',
    () async {
      await build(online: true).recordFailedDelivery(
        'o2',
        reasonCode: 'wrong_address',
        resolutionAction: 'reschedule',
      );

      final op = (await onlyOpOrNull())!;
      expect(op.type, 'order_failed_delivery');
      final body = jsonDecode(op.payload)['body'] as Map<String, dynamic>;
      expect(body['reason_code'], 'wrong_address');
      expect(body['resolution_action'], 'reschedule');
    },
  );

  test(
    'declareCashHandover queues a cash_handover_declare op keyed by route',
    () async {
      await build(online: true).declareCashHandover(
        routeId: 'r1',
        driverId: 'd1',
        actualAmount: 1234.5,
      );

      final op = (await onlyOpOrNull())!;
      expect(op.type, 'cash_handover_declare');
      expect(jsonDecode(op.payload)['aggregateId'], 'r1');
      expect(
        (jsonDecode(op.payload)['body'] as Map)['actual_amount'],
        '1234.50',
      );
    },
  );

  test(
    'recordDelivery offline writes media and queues an order_deliver op',
    () async {
      adapter.offline = true;
      await cache.write('order', 'o3', {
        'id': 'o3',
        'status': 'out_for_delivery',
      });

      final outcome = await build(online: false).recordDelivery(
        orderId: 'o3',
        lines: _lines,
        otpCode: '123456',
        gpsLat: 1.0,
        gpsLng: 2.0,
        paymentMethod: 'cash',
        amountCollected: 900,
        signatureBytes: [1, 2, 3],
        photoBytes: [4, 5, 6],
      );

      expect(outcome, isA<DeliverQueued>());
      expect(media.keys, hasLength(2));
      expect((await cache.read('order', 'o3'))!['status'], 'delivered');

      final op = (await onlyOpOrNull())!;
      expect(op.type, 'order_deliver');
      final payload = jsonDecode(op.payload) as Map<String, dynamic>;
      expect(payload['path'], '/api/v1/orders/o3/deliver');
      expect(payload['uploadPath'], '/api/v1/orders/o3/pod-attachments');
      expect((payload['media'] as List), hasLength(2));
      expect(payload['body']['otp_code'], '123456');
      expect(
        payload['body']['proof_of_delivery']['signature_blob_ref'],
        isNull,
      );
    },
  );

  test('recordDelivery online delivers inline and queues nothing', () async {
    final outcome = await build(online: true).recordDelivery(
      orderId: 'o4',
      lines: _lines,
      otpCode: '123456',
      gpsLat: 1,
      gpsLng: 2,
      paymentMethod: 'cash',
      amountCollected: 0,
      signatureBytes: [1],
      photoBytes: [2],
    );

    expect(outcome, isA<DeliverSynced>());
    expect(await onlyOpOrNull(), isNull);
    expect(adapter.paths.where((p) => p.endsWith('/deliver')), hasLength(1));
  });

  test(
    'recordDelivery online with a rejected OTP surfaces DeliverFailed',
    () async {
      adapter.deliverStatus = 409;

      final outcome = await build(online: true).recordDelivery(
        orderId: 'o5',
        lines: _lines,
        otpCode: 'bad',
        gpsLat: 1,
        gpsLng: 2,
        paymentMethod: 'cash',
        amountCollected: 0,
        signatureBytes: [1],
        photoBytes: [2],
      );

      expect(outcome, isA<DeliverFailed>());
      expect((outcome as DeliverFailed).message, 'Wrong code.');
      expect(await onlyOpOrNull(), isNull);
    },
  );
}
