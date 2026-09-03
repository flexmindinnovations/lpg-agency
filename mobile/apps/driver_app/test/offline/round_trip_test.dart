import 'dart:convert';

import 'package:api_client/api_client.dart';
import 'package:dio/dio.dart';
import 'package:driver_app/src/offline/delivery_mutations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import '../support/offline_harness.dart';

/// A stub backend for the whole delivery workflow.
class _BackendStub implements HttpClientAdapter {
  bool offline = true;
  final calls = <String>[];

  @override
  Future<ResponseBody> fetch(RequestOptions options, _, _) async {
    if (offline) {
      throw DioException.connectionError(
        requestOptions: options,
        reason: 'no signal',
      );
    }
    calls.add(options.path);
    if (options.path.endsWith('/pod-attachments')) {
      return _json({'blob_ref': 'blob-${calls.length}'}, 201);
    }
    // /depart and /deliver both answer with an order body.
    return _json({'order': _order('delivered')}, 200);
  }

  @override
  void close({bool force = false}) {}
}

Map<String, dynamic> _order(String status) => {
  'id': 'order-1',
  'tenant_id': 't1',
  'branch_id': 'b1',
  'customer_id': 'c1',
  'address_id': 'a1',
  'delivery_address': {'address_line': '1 Test St'},
  'status': status,
  'booking_source': 'mobile_app',
  'requested_date': '2026-09-03T00:00:00Z',
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

void main() {
  test('offline depart + deliver, then drain when back online', () async {
    final backend = _BackendStub();
    final harness = OfflineHarness(
      ApiClient(baseUrl: 'https://api.test')..dio.httpClientAdapter = backend,
      online: false,
    );
    addTearDown(harness.dispose);

    // The stop was opened online earlier — its order is in the read cache.
    await harness.cache.write('order', 'order-1', _order('ready_for_dispatch'));

    final container = ProviderContainer(overrides: harness.overrides);
    addTearDown(container.dispose);
    final mutations = container.read(deliveryMutationsProvider);

    // --- Offline: work the stop ---
    await mutations.departStop('order-1');
    final delivered = await mutations.recordDelivery(
      orderId: 'order-1',
      lines: const [],
      otpCode: '123456',
      gpsLat: 1,
      gpsLng: 2,
      paymentMethod: 'cash',
      amountCollected: 0,
      signatureBytes: const [1, 2, 3],
      photoBytes: const [4, 5, 6],
    );

    expect(delivered, isA<DeliverQueued>());
    expect(backend.calls, isEmpty); // nothing reached the server
    expect(harness.media.keys, hasLength(2)); // POD media held locally

    // Let the fire-and-forget syncNow() from enqueue exhaust itself offline.
    await Future<void>.delayed(const Duration(milliseconds: 50));

    // The optimistic local state a pending-aware read would surface.
    expect(
      (await harness.cache.read('order', 'order-1'))!['status'],
      'delivered',
    );

    final queued = await harness.ops();
    expect(queued.map((o) => o.type).toSet(), {
      'order_depart',
      'order_deliver',
    });
    expect(queued.every((o) => o.status != 'synced'), isTrue);
    // Every queued op carries the aggregate id the overlay keys on.
    for (final op in queued) {
      expect(jsonDecode(op.payload)['aggregateId'], 'order-1');
    }

    // --- Back online: the queue drains ---
    backend.offline = false;
    await harness.coordinator.syncNow(ignoreBackoff: true);
    await Future<void>.delayed(const Duration(milliseconds: 50));

    expect(backend.calls, [
      '/api/v1/orders/order-1/depart',
      '/api/v1/orders/order-1/pod-attachments',
      '/api/v1/orders/order-1/pod-attachments',
      '/api/v1/orders/order-1/deliver',
    ]);
    for (final op in await harness.ops()) {
      expect(op.status, 'synced');
    }
    expect(harness.media.keys, isEmpty); // uploaded, then cleaned up
  });
}
