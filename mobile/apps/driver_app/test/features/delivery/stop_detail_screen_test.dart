import 'dart:convert';
import 'dart:typed_data';

import 'package:api_client/api_client.dart';
import 'package:design_system/design_system.dart';
import 'package:dio/dio.dart';
import 'package:driver_app/src/features/delivery/data/driver_position_provider.dart';
import 'package:driver_app/src/features/delivery/data/stop_destination_provider.dart';
import 'package:driver_app/src/features/delivery/data/stop_order_provider.dart';
import 'package:driver_app/src/features/delivery/presentation/stop_detail_screen.dart';
import 'package:driver_app/src/features/delivery/presentation/widgets/stop_map_card.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:maps/maps.dart';
import 'package:maps/maps_testing.dart';

import '../../support/offline_harness.dart';

OrderResponse _order({String status = 'out_for_delivery'}) => OrderResponse(
  id: 'abcdef01aaaabbbb',
  orderNumber: 'ORD000042',
  tenantId: 't1',
  branchId: 'b1',
  customerId: 'c1',
  addressId: 'a1',
  deliveryAddress: const DeliveryAddressPayload(addressLine: '12 Baker Street'),
  status: status,
  bookingSource: 'mobile_app',
  requestedDate: DateTime(2026, 9, 1),
  metadata: const {},
  totalAmount: 950,
  lines: const [
    OrderLineResponse(
      id: 'l1',
      cylinderTypeId: 'ct1',
      quantityOrdered: 2,
      quantityDelivered: 0,
      quantityPending: 2,
      quantityCollectedEmpty: 0,
      isBackordered: false,
    ),
  ],
);

Map<String, dynamic> _orderJson({String status = 'out_for_delivery'}) => {
  'id': 'abcdef01aaaabbbb',
  'order_number': 'ORD000042',
  'tenant_id': 't1',
  'branch_id': 'b1',
  'customer_id': 'c1',
  'address_id': 'a1',
  'delivery_address': {'address_line': '12 Baker Street'},
  'status': status,
  'booking_source': 'mobile_app',
  'requested_date': '2026-09-01T00:00:00Z',
  'metadata': <String, dynamic>{},
  'total_amount': 950,
  'lines': const <dynamic>[],
};

/// Records every request and returns a canned order.
class _RecordingAdapter implements HttpClientAdapter {
  _RecordingAdapter({String status = 'out_for_delivery'})
    : _body = jsonEncode(_orderJson(status: status));

  final calls = <RequestOptions>[];
  final String _body;

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    calls.add(options);
    return ResponseBody.fromString(
      _body,
      200,
      headers: {
        Headers.contentTypeHeader: [Headers.jsonContentType],
      },
    );
  }

  @override
  void close({bool force = false}) {}
}

/// Keeps the stop-detail map card off the network/geolocator in these tests.
final _mapOverrides = [
  stopDestinationProvider.overrideWith(
    (ref, id) async => const StopDestination(
      point: LatLng(51.52, -0.15),
      label: '12 Baker Street',
      isApproximate: false,
    ),
  ),
  driverPositionProvider.overrideWith((ref) async => null),
  mapTileProviderProvider.overrideWithValue(FakeTileProvider()),
];

Widget _host(ProviderContainer container) => UncontrolledProviderScope(
  container: container,
  child: MaterialApp(
    theme: LpgTheme.light,
    home: const StopDetailScreen(orderId: 'abcdef01aaaabbbb'),
  ),
);

/// The stop-detail list is now tall (map card + actions) — give the tester a
/// tall viewport so nothing lands off-screen in the lazy `ListView`.
Future<void> _pump(WidgetTester tester, ProviderContainer container) async {
  tester.view.physicalSize = const Size(1000, 2600);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.reset);
  await tester.pumpWidget(_host(container));
  await tester.pumpAndSettle();
}

void main() {
  group('StopDetailScreen', () {
    testWidgets('shows the order summary and delivery actions', (tester) async {
      final container = ProviderContainer(
        overrides: [
          ..._mapOverrides,
          stopOrderProvider.overrideWith((ref, id) async => _order()),
        ],
      );
      addTearDown(container.dispose);

      await _pump(tester, container);

      expect(find.text('ORD000042'), findsOneWidget);
      expect(find.text('12 Baker Street'), findsOneWidget);
      expect(find.textContaining('2 cylinders'), findsOneWidget);
      expect(find.textContaining('Collect ₹950'), findsOneWidget);
      expect(find.byType(StopMapCard), findsOneWidget);
      expect(find.widgetWithText(LpgButton, 'Navigate'), findsOneWidget);
      expect(find.text('Record delivery'), findsOneWidget);
      expect(find.text('Delivery failed'), findsOneWidget);
    });

    testWidgets('"Start this delivery" queues an order_depart op', (
      tester,
    ) async {
      final adapter = _RecordingAdapter(status: 'ready_for_dispatch');
      final harness = OfflineHarness(
        ApiClient(baseUrl: 'https://api.test')..dio.httpClientAdapter = adapter,
      );
      addTearDown(harness.dispose);
      final container = ProviderContainer(
        overrides: [
          ..._mapOverrides,
          ...harness.overrides,
          stopOrderProvider.overrideWith(
            (ref, id) async => _order(status: 'ready_for_dispatch'),
          ),
        ],
      );
      addTearDown(container.dispose);

      await _pump(tester, container);

      await tester.tap(find.text('Start this delivery'));
      await tester.pumpAndSettle();

      final ops = await harness.ops();
      expect(ops.single.type, 'order_depart');
      expect(
        jsonDecode(ops.single.payload)['path'],
        '/api/v1/orders/abcdef01aaaabbbb/depart',
      );
    });

    testWidgets('the failed-delivery sheet queues an op with the reason', (
      tester,
    ) async {
      final adapter = _RecordingAdapter();
      final harness = OfflineHarness(
        ApiClient(baseUrl: 'https://api.test')..dio.httpClientAdapter = adapter,
      );
      addTearDown(harness.dispose);
      final container = ProviderContainer(
        overrides: [
          ..._mapOverrides,
          ...harness.overrides,
          stopOrderProvider.overrideWith((ref, id) async => _order()),
        ],
      );
      addTearDown(container.dispose);

      await _pump(tester, container);

      await tester.tap(find.text('Delivery failed'));
      await tester.pumpAndSettle();
      expect(find.text('Why did the delivery fail?'), findsOneWidget);

      await tester.tap(find.text('Customer unavailable'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Confirm failed delivery'));
      await tester.pumpAndSettle();

      final ops = await harness.ops();
      expect(ops.single.type, 'order_failed_delivery');
      final body = jsonDecode(ops.single.payload)['body'] as Map;
      expect(body['reason_code'], 'customer_unavailable');
    });
  });
}
