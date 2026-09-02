import 'dart:convert';

import 'package:api_client/api_client.dart';
import 'package:design_system/design_system.dart';
import 'package:dio/dio.dart';
import 'package:driver_app/src/api_provider.dart';
import 'package:driver_app/src/features/delivery/data/image_picker_provider.dart';
import 'package:driver_app/src/features/delivery/data/location_sharing.dart';
import 'package:driver_app/src/features/delivery/data/stop_order_provider.dart';
import 'package:driver_app/src/features/delivery/presentation/record_delivery_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:geolocator/geolocator.dart';
import 'package:go_router/go_router.dart';
import 'package:image_picker/image_picker.dart';
import 'package:signature/signature.dart';

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

  @override
  Future<ResponseBody> fetch(RequestOptions options, _, _) async {
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

ProviderContainer _container(_RecordingAdapter adapter) {
  final client = ApiClient(baseUrl: 'https://api.test')
    ..dio.httpClientAdapter = adapter;
  return ProviderContainer(
    overrides: [
      apiClientProvider.overrideWithValue(client),
      stopOrderProvider.overrideWith((ref, id) async => _order()),
      imagePickerProvider.overrideWithValue(_FakePicker()),
      driverGeolocatorProvider.overrideWithValue(const _FakeGeolocator()),
    ],
  );
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
      final c = _container(_RecordingAdapter());
      addTearDown(c.dispose);
      await _pump(tester, c);

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
      final c = _container(adapter);
      addTearDown(c.dispose);
      await _pump(tester, c);

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
      final c = _container(adapter);
      addTearDown(c.dispose);
      await _pump(tester, c);

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
  });
}
