import 'dart:async';
import 'dart:convert';

import 'package:api_client/api_client.dart';
import 'package:design_system/design_system.dart';
import 'package:dio/dio.dart';
import 'package:driver_app/src/api_provider.dart';
import 'package:driver_app/src/dev_otp_provider.dart';
import 'package:driver_app/src/features/delivery/data/active_route_provider.dart';
import 'package:driver_app/src/features/delivery/data/held_empties_provider.dart';
import 'package:driver_app/src/features/delivery/data/image_picker_provider.dart';
import 'package:driver_app/src/features/delivery/data/location_sharing.dart';
import 'package:driver_app/src/features/delivery/data/stop_order_provider.dart';
import 'package:driver_app/src/features/delivery/presentation/record_delivery_screen.dart';
import 'package:driver_app/src/features/van_load/data/van_load_provider.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:geolocator/geolocator.dart';
import 'package:go_router/go_router.dart';
import 'package:image_picker/image_picker.dart';
import 'package:signature/signature.dart';

import '../../support/offline_harness.dart';

OrderResponse _order({double? tax, double? payable}) => OrderResponse(
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
  taxAmount: tax,
  payableAmount: payable,
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

  /// When set, `POST /deliver` answers 409 with this message.
  String? deliverRefusal;

  /// The answer to `GET /orders/{id}/settlement`; `null` = not reachable.
  Map<String, dynamic>? settlement;

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
    if (options.path.endsWith('/settlement')) {
      final answer = settlement;
      if (answer == null) {
        return ResponseBody.fromString('{}', 500);
      }
      return ResponseBody.fromString(
        jsonEncode(answer),
        200,
        headers: {
          Headers.contentTypeHeader: [Headers.jsonContentType],
        },
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
      final refusal = deliverRefusal;
      return ResponseBody.fromString(
        jsonEncode(
          refusal == null
              ? {'order': _orderJson()}
              : {'error_code': 'EMPTIES_EXCEED_HELD', 'detail': refusal},
        ),
        refusal == null ? 200 : 409,
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
  const _FakeGeolocator({
    this.permission = LocationPermission.whileInUse,
    this.hangs = false,
  });

  final LocationPermission permission;

  /// Never answers — a phone that can't see the sky.
  final bool hangs;

  @override
  Future<bool> serviceEnabled() async => true;

  @override
  Future<LocationPermission> ensurePermission() async => permission;

  @override
  Future<Position> currentPosition() async => hangs
      ? Completer<Position>().future
      : Position(
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

HeldEmpties _held(String id, String name, int quantity) => HeldEmpties(
  cylinderTypeId: id,
  cylinderTypeName: name,
  quantityHeld: quantity,
);

/// An agency with UPI, a gateway and a credit limit set up.
const _agencyMethods = PaymentMethods(
  booking: [],
  delivery: [
    PaymentMethodOption(code: 'cash', label: 'Cash'),
    PaymentMethodOption(code: 'upi', label: 'UPI'),
    PaymentMethodOption(code: 'online_gateway', label: 'Online payment'),
    PaymentMethodOption(code: 'credit', label: 'On credit'),
  ],
  office: [],
);

({ProviderContainer container, OfflineHarness harness}) _container(
  _RecordingAdapter adapter, {
  bool online = true,
  List<HeldEmpties>? Function()? held,
  String? devCode,
  DriverGeolocator geolocator = const _FakeGeolocator(),
  OrderResponse? order,
  PaymentMethods methods = _agencyMethods,
}) {
  final harness = OfflineHarness(
    ApiClient(baseUrl: 'https://api.test')..dio.httpClientAdapter = adapter,
    online: online,
  );
  final container = ProviderContainer(
    overrides: [
      ...harness.overrides,
      stopOrderProvider.overrideWith((ref, id) async => order ?? _order()),
      paymentMethodsProvider.overrideWith((ref) async => methods),
      imagePickerProvider.overrideWithValue(_FakePicker()),
      driverGeolocatorProvider.overrideWithValue(geolocator),
      activeRouteProvider.overrideWith((ref) async => null),
      // `null` = never loaded on this phone.
      heldEmptiesProvider.overrideWith((ref, id) async => held?.call()),
      cylinderTypeNamesProvider.overrideWith((ref) async => {'ct1': '14.2 kg'}),
      devDeliveryOtpLookupProvider.overrideWithValue((_) async => devCode),
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
      expect(find.text("Customer's signature (optional)"), findsOneWidget);
      expect(find.text('Delivery photo (optional)'), findsOneWidget);
      expect(find.text('Take a photo'), findsOneWidget);
      expect(find.text('Complete delivery'), findsOneWidget);
      // Amount prefilled from the order total.
      expect(find.text('905.50'), findsOneWidget);
    });

    testWidgets('offers only the payment methods the agency has set up', (
      tester,
    ) async {
      final (:container, :harness) = _container(
        _RecordingAdapter(),
        methods: const PaymentMethods(
          booking: [],
          delivery: [PaymentMethodOption(code: 'cash', label: 'Cash')],
          office: [],
        ),
      );
      addTearDown(harness.dispose);
      addTearDown(container.dispose);
      await _pump(tester, container);

      await tester.tap(find.text('Cash'));
      await tester.pumpAndSettle();

      expect(find.text('UPI'), findsNothing);
      expect(find.text('On credit'), findsNothing);
      expect(find.text('Card'), findsNothing);
    });

    testWidgets('prefills the amount with the price plus GST', (tester) async {
      final (:container, :harness) = _container(
        _RecordingAdapter(),
        order: _order(tax: 45.28, payable: 950.78),
      );
      addTearDown(harness.dispose);
      addTearDown(container.dispose);
      await _pump(tester, container);

      // Rs 905.50 plus Rs 45.28 GST: what the customer pays, and what the
      // UPI QR (built from the invoice) asks for.
      expect(find.text('950.78'), findsOneWidget);
      expect(find.text('905.50'), findsNothing);
    });

    testWidgets('shows what was already paid online and asks for no cash', (
      tester,
    ) async {
      final adapter = _RecordingAdapter()
        ..settlement = {
          'order_id': 'order-1',
          'payable_amount': '905.50',
          'paid_online_amount': '905.50',
          'balance_due': '0.00',
        };
      final (:container, :harness) = _container(adapter);
      addTearDown(harness.dispose);
      addTearDown(container.dispose);
      await _pump(tester, container);

      expect(find.text('Already paid online'), findsOneWidget);
      expect(find.text('Amount collected'), findsNothing);
      await tester.enterText(
        find.widgetWithText(TextField, 'Code from the customer'),
        '123456',
      );
      await tester.tap(find.text('Complete delivery'));
      await tester.runAsync(
        () => Future<void>.delayed(const Duration(seconds: 1)),
      );
      await tester.pumpAndSettle();

      final pod = adapter.deliverBody!['proof_of_delivery'] as Map;
      expect(pod['amount_collected'], 0);
      expect(pod['payment_method'], 'online_gateway');
    });

    testWidgets('will not complete until the balance is collected', (
      tester,
    ) async {
      final adapter = _RecordingAdapter();
      final (:container, :harness) = _container(adapter);
      addTearDown(harness.dispose);
      addTearDown(container.dispose);
      await _pump(tester, container);

      await tester.enterText(find.byType(TextField).first, '100');
      await tester.pumpAndSettle();

      expect(find.text('Payment not settled'), findsOneWidget);
      await tester.tap(find.text('Complete delivery'));
      await tester.pumpAndSettle();
      expect(adapter.deliverBody, isNull);

      // A partial payment with the rest on the customer's account.
      await tester.tap(find.byType(Switch));
      await tester.pumpAndSettle();
      expect(find.text('Payment not settled'), findsNothing);
      await tester.enterText(
        find.widgetWithText(TextField, 'Code from the customer'),
        '123456',
      );
      await tester.tap(find.text('Complete delivery'));
      await tester.runAsync(
        () => Future<void>.delayed(const Duration(seconds: 1)),
      );
      await tester.pumpAndSettle();

      final pod = adapter.deliverBody!['proof_of_delivery'] as Map;
      expect(pod['amount_collected'], 100);
      expect(pod['balance_on_account'], true);
    });

    testWidgets('on credit records no cash', (tester) async {
      final adapter = _RecordingAdapter();
      final (:container, :harness) = _container(adapter);
      addTearDown(harness.dispose);
      addTearDown(container.dispose);
      await _pump(tester, container);

      await tester.tap(find.text('Cash'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('On credit').last);
      await tester.pumpAndSettle();
      expect(find.text('Amount collected'), findsNothing);
      await tester.enterText(
        find.widgetWithText(TextField, 'Code from the customer'),
        '123456',
      );
      await tester.tap(find.text('Complete delivery'));
      await tester.runAsync(
        () => Future<void>.delayed(const Duration(seconds: 1)),
      );
      await tester.pumpAndSettle();

      final pod = adapter.deliverBody!['proof_of_delivery'] as Map;
      expect(pod['payment_method'], 'credit');
      expect(pod['amount_collected'], 0);
    });

    testWidgets('delivers without a signature or photo', (tester) async {
      final adapter = _RecordingAdapter();
      final (:container, :harness) = _container(adapter);
      addTearDown(harness.dispose);
      addTearDown(container.dispose);
      await _pump(tester, container);

      await tester.enterText(
        find.widgetWithText(TextField, 'Code from the customer'),
        '123456',
      );
      await tester.tap(find.text('Complete delivery'));
      await tester.runAsync(
        () => Future<void>.delayed(const Duration(seconds: 1)),
      );
      await tester.pumpAndSettle();

      // Nothing to upload: straight to the deliver call, with no refs.
      expect(adapter.paths, ['/api/v1/orders/order-1/deliver']);
      final pod = adapter.deliverBody!['proof_of_delivery'] as Map;
      expect(pod.containsKey('signature_blob_ref'), isFalse);
      expect(pod.containsKey('photo_blob_ref'), isFalse);
      expect(find.text('home'), findsOneWidget);
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
      await tester.tap(find.text('Complete delivery'));
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

      await tester.tap(find.text('Complete delivery'));
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

    testWidgets('a missing code is shown beside Confirm, not at the top', (
      tester,
    ) async {
      final adapter = _RecordingAdapter();
      final (:container, :harness) = _container(adapter);
      addTearDown(harness.dispose);
      addTearDown(container.dispose);
      await _pump(tester, container);

      await tester.tap(find.text('Complete delivery'));
      await tester.pumpAndSettle();

      expect(adapter.paths, isEmpty);
      final banner = find.widgetWithText(
        LpgBanner,
        'Enter the delivery code the customer received.',
      );
      expect(banner, findsOneWidget);
      // The banner sits directly above the button, below the photo section.
      final bannerTop = tester.getTopLeft(banner).dy;
      expect(
        bannerTop,
        greaterThan(tester.getTopLeft(find.text('Take a photo')).dy),
      );
      expect(
        bannerTop,
        lessThan(tester.getTopLeft(find.text('Complete delivery')).dy),
      );
    });

    testWidgets('denied location permission blocks with a clear message', (
      tester,
    ) async {
      final adapter = _RecordingAdapter();
      final (:container, :harness) = _container(
        adapter,
        geolocator: const _FakeGeolocator(
          permission: LocationPermission.denied,
        ),
      );
      addTearDown(harness.dispose);
      addTearDown(container.dispose);
      await _pump(tester, container);

      await tester.enterText(
        find.widgetWithText(TextField, 'Code from the customer'),
        '123456',
      );
      await tester.tap(find.text('Complete delivery'));
      await tester.pumpAndSettle();

      expect(adapter.paths, isEmpty);
      expect(
        find.widgetWithText(
          LpgBanner,
          'Allow location access — a delivery needs a GPS stamp.',
        ),
        findsOneWidget,
      );
      // Still on the form so the driver can retry.
      expect(find.text('Complete delivery'), findsOneWidget);
    });

    test('deliveryFix gives up with a retryable message on timeout', () async {
      const geolocator = _FakeGeolocator(hangs: true);
      await expectLater(
        geolocator.deliveryFix(timeLimit: const Duration(milliseconds: 10)),
        throwsA(
          isA<GpsFixException>().having(
            (e) => e.message,
            'message',
            contains("Couldn't get a GPS fix"),
          ),
        ),
      );
    });

    testWidgets('"Send a new code" asks the server to resend the code', (
      tester,
    ) async {
      final adapter = _RecordingAdapter();
      final (:container, :harness) = _container(adapter);
      addTearDown(harness.dispose);
      addTearDown(container.dispose);
      await _pump(tester, container);

      await tester.tap(find.text('Send a new code'));
      await tester.runAsync(
        () => Future<void>.delayed(const Duration(milliseconds: 200)),
      );
      await tester.pumpAndSettle();

      expect(adapter.paths, ['/api/v1/orders/order-1/delivery-otp']);
      expect(find.text('A new code was sent to the customer.'), findsOneWidget);
    });

    testWidgets('testing builds show the customer\'s code', (tester) async {
      final (:container, :harness) = _container(
        _RecordingAdapter(),
        devCode: '482913',
      );
      addTearDown(harness.dispose);
      addTearDown(container.dispose);
      await _pump(tester, container);

      expect(find.byKey(LpgDevOtpBanner.codeKey), findsOneWidget);
      expect(find.text('482913'), findsOneWidget);
    });

    // The stepper in the card for one cylinder size.
    Finder stepper(String size, String label) => find.byWidgetPredicate(
      (w) => w is LpgQuantityStepper && w.semanticLabel == '$label, $size',
    );
    int valueOf(WidgetTester tester, String size, [String? label]) => tester
        .widget<LpgQuantityStepper>(stepper(size, label ?? 'Empties collected'))
        .value;
    Future<void> step(
      WidgetTester tester,
      String size,
      IconData button, {
      String label = 'Empties collected',
      int times = 1,
    }) async {
      for (var i = 0; i < times; i++) {
        await tester.tap(
          find.descendant(
            of: stepper(size, label),
            matching: find.byIcon(button),
          ),
        );
        await tester.pumpAndSettle();
      }
    }

    Future<void> complete(WidgetTester tester) async {
      await tester.enterText(
        find.widgetWithText(TextField, 'Code from the customer'),
        '123456',
      );
      await tester.tap(find.text('Complete delivery'));
      await tester.runAsync(
        () => Future<void>.delayed(const Duration(seconds: 1)),
      );
      await tester.pumpAndSettle();
    }

    testWidgets('the cylinder cards fit a small phone with long size names', (
      tester,
    ) async {
      final (:container, :harness) = _container(
        _RecordingAdapter(),
        held: () => [
          _held('ct1', 'Commercial 47.5 kg liquid off-take cylinder', 120),
          _held('ct2', 'Domestic 14.2 kg composite cylinder', 99),
        ],
      );
      addTearDown(harness.dispose);
      addTearDown(container.dispose);
      tester.view.physicalSize = const Size(320, 4000);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.reset);

      // A layout overflow fails the test.
      await tester.pumpWidget(_host(container));
      await tester.pumpAndSettle();

      expect(find.byType(LpgQuantityStepper), findsNWidgets(3));
    });

    testWidgets('collects empties from earlier deliveries, of any size held', (
      tester,
    ) async {
      final adapter = _RecordingAdapter();
      final (:container, :harness) = _container(
        adapter,
        held: () => [
          _held('ct1', '14.2 kg', 10),
          _held('ct2', '19 kg', 3),
          _held('ct3', '5 kg', 0),
        ],
      );
      addTearDown(harness.dispose);
      addTearDown(container.dispose);
      await _pump(tester, container);

      expect(
        find.text('Ordered: 2 · up to 10 empties to collect'),
        findsOneWidget,
      );
      expect(
        find.text('Not on this order · up to 3 empties to collect'),
        findsOneWidget,
      );
      // A size neither ordered nor held gets no card.
      expect(find.text('5 kg'), findsNothing);
      // One empty per cylinder is filled in; other sizes start at none.
      expect(valueOf(tester, '14.2 kg'), 2);
      expect(valueOf(tester, '19 kg'), 0);

      // More than today's two, up to what was held.
      await step(tester, '14.2 kg', LpgIcons.add, times: 8);
      expect(valueOf(tester, '14.2 kg'), 10);
      expect(
        tester
            .widget<LpgQuantityStepper>(stepper('14.2 kg', 'Empties collected'))
            .max,
        10,
      );
      await step(tester, '19 kg', LpgIcons.add, times: 2);
      await complete(tester);

      final line = (adapter.deliverBody!['lines'] as List).single as Map;
      expect(line['quantity_delivered'], 2);
      expect(line['quantity_collected_empty'], 10);
      expect(adapter.deliverBody!['other_empties'], [
        {'cylinder_type_id': 'ct2', 'quantity': 2},
      ]);
    });

    testWidgets('delivering fewer does not limit the earlier empties', (
      tester,
    ) async {
      final adapter = _RecordingAdapter();
      final (:container, :harness) = _container(
        adapter,
        held: () => [_held('ct1', '14.2 kg', 5)],
      );
      addTearDown(harness.dispose);
      addTearDown(container.dispose);
      await _pump(tester, container);

      await step(tester, '14.2 kg', LpgIcons.add, times: 3);
      await step(tester, '14.2 kg', LpgIcons.remove, label: 'Delivered');

      expect(valueOf(tester, '14.2 kg', 'Delivered'), 1);
      expect(valueOf(tester, '14.2 kg'), 5);
    });

    testWidgets('a customer holding nothing has nothing to give back', (
      tester,
    ) async {
      final adapter = _RecordingAdapter();
      final (:container, :harness) = _container(
        adapter,
        held: () => [_held('ct1', '14.2 kg', 0)],
      );
      addTearDown(harness.dispose);
      addTearDown(container.dispose);
      await _pump(tester, container);

      expect(
        find.text('Ordered: 2 · no earlier empties to collect'),
        findsOneWidget,
      );
      expect(valueOf(tester, '14.2 kg'), 0);
      await complete(tester);

      final line = (adapter.deliverBody!['lines'] as List).single as Map;
      expect(line['quantity_collected_empty'], 0);
      expect(adapter.deliverBody!.containsKey('other_empties'), isFalse);
    });

    testWidgets('without the held figures nothing is filled in', (
      tester,
    ) async {
      final adapter = _RecordingAdapter();
      final (:container, :harness) = _container(adapter);
      addTearDown(harness.dispose);
      addTearDown(container.dispose);
      await _pump(tester, container);

      expect(find.text('14.2 kg'), findsOneWidget);
      expect(
        find.textContaining('empties could not be checked'),
        findsOneWidget,
      );
      expect(valueOf(tester, '14.2 kg'), 0);

      // The old limit: no more than are delivered here.
      await step(tester, '14.2 kg', LpgIcons.add, times: 2);
      await step(tester, '14.2 kg', LpgIcons.remove, label: 'Delivered');
      await complete(tester);

      final line = (adapter.deliverBody!['lines'] as List).single as Map;
      expect(line['quantity_collected_empty'], 1);
    });

    testWidgets('a refused delivery reads the held figures again', (
      tester,
    ) async {
      var held = 5;
      final adapter = _RecordingAdapter()
        ..deliverRefusal = 'This customer had 1 empty cylinder to give back.';
      final (:container, :harness) = _container(
        adapter,
        held: () => [_held('ct1', '14.2 kg', held)],
      );
      addTearDown(harness.dispose);
      addTearDown(container.dispose);
      await _pump(tester, container);
      expect(valueOf(tester, '14.2 kg'), 2);

      held = 1;
      await complete(tester);

      expect(
        find.widgetWithText(
          LpgBanner,
          'This customer had 1 empty cylinder to give back.',
        ),
        findsOneWidget,
      );
      expect(valueOf(tester, '14.2 kg'), 1);
    });
  });
}
