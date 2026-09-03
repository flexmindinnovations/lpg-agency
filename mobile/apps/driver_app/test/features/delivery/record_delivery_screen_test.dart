import 'dart:convert';

import 'package:api_client/api_client.dart';
import 'package:design_system/design_system.dart';
import 'package:dio/dio.dart';
import 'package:driver_app/src/features/delivery/data/active_route_provider.dart';
import 'package:driver_app/src/features/delivery/data/image_picker_provider.dart';
import 'package:driver_app/src/features/delivery/data/location_sharing.dart';
import 'package:driver_app/src/features/delivery/data/stop_order_provider.dart';
import 'package:driver_app/src/features/delivery/presentation/record_delivery_screen.dart';
import 'package:driver_app/src/offline/pending_sync.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:geolocator/geolocator.dart';
import 'package:go_router/go_router.dart';
import 'package:image_picker/image_picker.dart';
import 'package:signature/signature.dart';

import '../../support/offline_harness.dart';

OrderResponse _order() => OrderResponse(
  id: 'order-1',
  orderNumber: 'ORD000042',
  tenantId: 't1',
  branchId: 'b1',
  customerId: 'c1',
  addressId: 'a1',
  deliveryAddress: const DeliveryAddressPayload(addressLine: '12 Baker Street'),
  status: 'out_for_delivery',
  bookingSource: 'mobile_app',
  requestedDate: DateTime(2026, 9, 1),
  metadata: const {},
  totalAmount: 905.5,
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

class _RecordingAdapter implements HttpClientAdapter {
  final paths = <String>[];
  Map<String, dynamic>? deliverBody;

  /// When true, every request fails as if the network is down — so the
  /// coordinator's post-enqueue `syncNow()` can't quietly complete the op.
  bool offline = false;

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
      return ResponseBody.fromString(
        jsonEncode({'blob_ref': 'blob-${paths.length}'}),
        201,
        headers: {
          Headers.contentTypeHeader: [Headers.jsonContentType],
        },
      );
    }
    if (options.path.endsWith('/deliver')) {
      deliverBody = options.data as Map<String, dynamic>;
      return ResponseBody.fromString(
        jsonEncode({'order': _orderJson()}),
        200,
        headers: {
          Headers.contentTypeHeader: [Headers.jsonContentType],
        },
      );
    }
    return ResponseBody.fromString('{}', 200);
  }

  @override
  void close({bool force = false}) {}
}

Map<String, dynamic> _orderJson() => {
  'id': 'order-1',
  'order_number': 'ORD000042',
  'tenant_id': 't1',
  'branch_id': 'b1',
  'customer_id': 'c1',
  'address_id': 'a1',
  'delivery_address': {'address_line': '12 Baker Street'},
  'status': 'delivered',
  'booking_source': 'mobile_app',
  'requested_date': '2026-09-01T00:00:00Z',
  'metadata': <String, dynamic>{},
  'total_amount': 905.5,
  'lines': const <dynamic>[],
};

class _FakeGeolocator extends DriverGeolocator {
  const _FakeGeolocator();
  @override
  Future<Position> currentPosition() async => Position(
    latitude: 17.44,
    longitude: 78.35,
    timestamp: DateTime(2026, 9, 1),
    accuracy: 5,
    altitude: 0,
    altitudeAccuracy: 0,
    heading: 0,
    headingAccuracy: 0,
    speed: 0,
    speedAccuracy: 0,
  );
}

// A valid 1x1 transparent PNG so `Image.memory` can decode it in the tester.
final _pngPixel = base64Decode(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==',
);

class _FakePicker implements ImagePicker {
  @override
  Future<XFile?> pickImage({
    required ImageSource source,
    double? maxWidth,
    double? maxHeight,
    int? imageQuality,
    CameraDevice preferredCameraDevice = CameraDevice.rear,
    bool requestFullMetadata = true,
  }) async =>
      XFile.fromData(_pngPixel, name: 'photo.png', mimeType: 'image/png');

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

Widget _host(ProviderContainer c) => UncontrolledProviderScope(
  container: c,
  child: MaterialApp.router(
    theme: LpgTheme.light,
    routerConfig: GoRouter(
      initialLocation: '/deliver',
      routes: [
        GoRoute(
          path: '/',
          builder: (_, _) => const Scaffold(body: Text('home')),
        ),
        GoRoute(
          path: '/deliver',
          builder: (_, _) => const RecordDeliveryScreen(orderId: 'order-1'),
        ),
      ],
    ),
  ),
);

RouteSummary _route({List<RouteLoadLine> loadedLines = const []}) =>
    RouteSummary(
      id: 'route-1',
      status: 'in_progress',
      driverId: 'd1',
      vehicleId: 'v1',
      stops: const [
        RouteStopSummary(
          id: 's1',
          orderId: 'order-1',
          sequenceNumber: 1,
          status: 'out_for_delivery',
        ),
      ],
      loadedLines: loadedLines,
    );

({ProviderContainer container, OfflineHarness harness}) _container(
  _RecordingAdapter adapter, {
  bool online = true,
  RouteSummary? route,
  Map<String, int> queuedEmpties = const {},
}) {
  final harness = OfflineHarness(
    ApiClient(baseUrl: 'https://api.test')..dio.httpClientAdapter = adapter,
    online: online,
  );
  final container = ProviderContainer(
    overrides: [
      ...harness.overrides,
      stopOrderProvider.overrideWith((ref, id) async => _order()),
      imagePickerProvider.overrideWithValue(_FakePicker()),
      driverGeolocatorProvider.overrideWithValue(const _FakeGeolocator()),
      activeRouteProvider.overrideWith((ref) async => route),
      // A plain stream — the screen watches this live drift-backed provider,
      // and `pumpAndSettle` would hang on the coordinator's queue watch.
      queuedEmptiesByTypeProvider.overrideWith(
        (ref) => Stream.value(queuedEmpties),
      ),
    ],
  );
  return (container: container, harness: harness);
}

Future<void> _pump(WidgetTester tester, ProviderContainer c) async {
  tester.view.physicalSize = const Size(1200, 4000);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.reset);
  await tester.pumpWidget(_host(c));
  await tester.pumpAndSettle();
}

void main() {
  group('RecordDeliveryScreen', () {
    testWidgets('renders the capture sections', (tester) async {
      final (:container, :harness) = _container(_RecordingAdapter());
      addTearDown(harness.dispose);
      addTearDown(container.dispose);
      await _pump(tester, container);

      expect(find.text('Cylinders'), findsOneWidget);
      expect(find.text('Payment'), findsOneWidget);
      expect(find.text('Delivery code'), findsOneWidget);
      expect(find.text("Customer's signature"), findsOneWidget);
      expect(find.text('Delivery photo'), findsOneWidget);
      expect(find.text('Take a photo'), findsOneWidget);
      expect(find.text('Confirm delivery'), findsOneWidget);
      // Amount prefilled from the order total.
      expect(find.text('905.50'), findsOneWidget);
    });

    testWidgets('blocks submit until a signature and photo are captured', (
      tester,
    ) async {
      final adapter = _RecordingAdapter();
      final (:container, :harness) = _container(adapter);
      addTearDown(harness.dispose);
      addTearDown(container.dispose);
      await _pump(tester, container);

      await tester.enterText(
        find.widgetWithText(TextField, 'Code from the customer'),
        '123456',
      );
      await tester.tap(find.text('Confirm delivery'));
      await tester.pumpAndSettle();

      expect(find.textContaining('signature and a photo'), findsOneWidget);
      expect(adapter.paths, isEmpty);
    });

    testWidgets('captures everything and posts the delivery', (tester) async {
      final adapter = _RecordingAdapter();
      final (:container, :harness) = _container(adapter);
      addTearDown(harness.dispose);
      addTearDown(container.dispose);
      await _pump(tester, container);

      // Signature stroke.
      final pad = find.byType(Signature);
      await tester.drag(pad, const Offset(40, 20));
      await tester.pump();
      // Photo.
      await tester.tap(find.text('Take a photo'));
      await tester.pumpAndSettle();
      // OTP.
      await tester.enterText(
        find.widgetWithText(TextField, 'Code from the customer'),
        '123456',
      );

      // Submitting encodes the signature PNG and talks to dio — both need a
      // real async zone, so drive it under runAsync.
      await tester.tap(find.text('Confirm delivery'));
      await tester.runAsync(
        () => Future<void>.delayed(const Duration(seconds: 1)),
      );
      await tester.pumpAndSettle();

      expect(
        adapter.paths,
        containsAllInOrder([
          '/api/v1/orders/order-1/pod-attachments',
          '/api/v1/orders/order-1/pod-attachments',
          '/api/v1/orders/order-1/deliver',
        ]),
      );
      final pod = adapter.deliverBody!['proof_of_delivery'] as Map;
      expect(pod['gps_lat'], 17.44);
      expect(pod['payment_method'], 'cash');
      expect(adapter.deliverBody!['otp_code'], '123456');

      // On success it leaves the stop entirely (a delivered order drops out
      // of the driver's visibility) and lands back on the route view.
      expect(find.byType(RecordDeliveryScreen), findsNothing);
      expect(find.text('home'), findsOneWidget);
    });

    testWidgets('offline: queues an order_deliver op and still lands home', (
      tester,
    ) async {
      final adapter = _RecordingAdapter()..offline = true;
      final (:container, :harness) = _container(adapter, online: false);
      addTearDown(harness.dispose);
      addTearDown(container.dispose);
      await _pump(tester, container);

      await tester.drag(find.byType(Signature), const Offset(40, 20));
      await tester.pump();
      await tester.tap(find.text('Take a photo'));
      await tester.pumpAndSettle();
      await tester.enterText(
        find.widgetWithText(TextField, 'Code from the customer'),
        '123456',
      );

      await tester.tap(find.text('Confirm delivery'));
      await tester.runAsync(
        () => Future<void>.delayed(const Duration(seconds: 1)),
      );
      await tester.pumpAndSettle();

      // No direct delivery POST — it's a queued op with local media.
      expect(adapter.paths.where((p) => p.endsWith('/deliver')), isEmpty);
      expect(harness.media.keys, hasLength(2));
      final ops = await harness.ops();
      expect(ops.single.type, 'order_deliver');

      expect(find.text('home'), findsOneWidget);
    });

    testWidgets('warns when empties collected exceed the van load manifest', (
      tester,
    ) async {
      final (:container, :harness) = _container(
        _RecordingAdapter(),
        route: _route(
          loadedLines: const [
            RouteLoadLine(cylinderTypeId: 'ct1', quantity: 1),
          ],
        ),
      );
      addTearDown(harness.dispose);
      addTearDown(container.dispose);
      await _pump(tester, container);

      // Prefill records 2 delivered / 2 empties for ct1; the van carried 1.
      expect(
        find.textContaining('more empties than the van was loaded with'),
        findsOneWidget,
      );

      // Step the empties down to the loaded quantity — warning clears.
      await tester.tap(
        find.descendant(
          of: find.widgetWithText(Row, 'Empties collected'),
          matching: find.byIcon(Icons.remove_circle_outline),
        ),
      );
      await tester.pump();
      expect(
        find.textContaining('more empties than the van was loaded with'),
        findsNothing,
      );
    });

    testWidgets('no manifest warning when the load covers the empties', (
      tester,
    ) async {
      final (:container, :harness) = _container(
        _RecordingAdapter(),
        route: _route(
          loadedLines: const [
            RouteLoadLine(cylinderTypeId: 'ct1', quantity: 5),
          ],
        ),
        queuedEmpties: const {'ct1': 1},
      );
      addTearDown(harness.dispose);
      addTearDown(container.dispose);
      await _pump(tester, container);

      // 1 queued elsewhere + 2 this stop = 3 <= 5 loaded.
      expect(
        find.textContaining('more empties than the van was loaded with'),
        findsNothing,
      );
    });
  });
}
