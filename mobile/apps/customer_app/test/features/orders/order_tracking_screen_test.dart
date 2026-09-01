import 'package:api_client/api_client.dart';
import 'package:customer_app/src/features/orders/data/order_tracking_provider.dart';
import 'package:customer_app/src/features/orders/data/orders_provider.dart';
import 'package:customer_app/src/features/orders/presentation/order_tracking_screen.dart';
import 'package:customer_app/src/widgets/location_map.dart';
import 'package:customer_app/src/widgets/map_tile_provider.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:latlong2/latlong.dart';

import '../../support/fake_tiles.dart';
import '../../support/pump_screen.dart';

const _destination = LatLng(9.9312, 76.2673);

OrderResponse _order() => OrderResponse(
  id: 'abcdef01aaaabbbb',
  orderNumber: 'ORD000042',
  tenantId: 't1',
  branchId: 'b1',
  customerId: 'c1',
  addressId: 'a1',
  deliveryAddress: const DeliveryAddressPayload(addressLine: '12 Baker Street'),
  status: 'out_for_delivery',
  bookingSource: 'mobile_app',
  requestedDate: DateTime(2026, 8, 20),
  metadata: const {},
  totalAmount: 500,
  lines: const [],
);

OrderTrackingView _view({
  LatLng? destination = _destination,
  bool approximate = false,
  String? routeStatus,
  DriverLocationSnapshot? lastKnown,
  TrackingDriver? driver,
}) => OrderTrackingView(
  destination: destination,
  destinationLabel: '12 Baker Street',
  destinationIsApproximate: approximate,
  status: 'out_for_delivery',
  routeStatus: routeStatus,
  lastKnownDriverLocation: lastKnown,
  driver: driver,
);

Widget _screen({
  OrderTrackingView? view,
  DriverPosition? driver,
}) => ProviderScope(
  overrides: [
    orderDetailProvider.overrideWith((ref, id) async => _order()),
    orderTrackingProvider.overrideWith((ref, id) async => view ?? _view()),
    driverLocationProvider.overrideWith((ref, id) => Stream.value(driver)),
    mapTileProviderProvider.overrideWithValue(FakeTileProvider()),
  ],
  child: MaterialApp(
    theme: LpgTheme.light,
    home: const OrderTrackingScreen(orderId: 'abcdef01aaaabbbb'),
  ),
);

void main() {
  group('OrderTrackingScreen', () {
    testWidgets('shows the map and the delivery milestones for a pinned address',
        (tester) async {
      await pumpScreen(tester, _screen(view: _view()));

      expect(find.byType(LocationMap), findsOneWidget);
      expect(find.text('Order Placed'), findsOneWidget);
      expect(find.text('Out for Delivery'), findsOneWidget);
    });

    testWidgets('shows the order number and a copyable tracking id', (
      tester,
    ) async {
      final copied = <String>[];
      tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(
        SystemChannels.platform,
        (call) async {
          if (call.method == 'Clipboard.setData') {
            copied.add((call.arguments as Map)['text'] as String);
          }
          return null;
        },
      );
      addTearDown(
        () => tester.binding.defaultBinaryMessenger
            .setMockMethodCallHandler(SystemChannels.platform, null),
      );

      await pumpScreen(tester, _screen(view: _view()));

      expect(find.text('ORD000042'), findsOneWidget);
      expect(find.text('ABCDEF01'), findsOneWidget); // shortened id

      await tester.tap(find.text('ABCDEF01'));
      await tester.pump();

      expect(copied, ['abcdef01aaaabbbb']); // the full id is copied
      expect(find.text('Tracking ID copied'), findsOneWidget);
    });

    testWidgets('shows an "approximate location" banner when geocoded', (
      tester,
    ) async {
      await pumpScreen(tester, _screen(view: _view(approximate: true)));

      expect(find.textContaining('Approximate location'), findsOneWidget);
    });

    testWidgets('shows the "not pinned" state when there is no location', (
      tester,
    ) async {
      await pumpScreen(tester, _screen(view: _view(destination: null)));

      expect(find.byType(LocationMap), findsNothing);
      expect(find.byType(MapUnavailable), findsOneWidget);
      expect(find.textContaining('map pin has not been set'), findsOneWidget);
      expect(find.text('Order Placed'), findsOneWidget);
    });

    testWidgets('waits for the driver location while the route is active', (
      tester,
    ) async {
      await pumpScreen(
        tester,
        _screen(view: _view(routeStatus: 'in_progress')),
      );

      expect(find.textContaining("Waiting for the driver's location"),
          findsOneWidget);
    });

    testWidgets('shows the driver name + vehicle, with a details sheet', (
      tester,
    ) async {
      await pumpScreen(
        tester,
        _screen(
          view: _view(
            routeStatus: 'in_progress',
            driver: const TrackingDriver(
              name: 'Ramesh Kumar',
              phoneNumber: '+91 90000 11111',
              vehicleNumber: 'TS07UB4412',
              vehicleModel: 'Tata Ace',
            ),
          ),
        ),
      );

      expect(find.text('Ramesh Kumar'), findsOneWidget);
      expect(find.textContaining('TS07UB4412'), findsOneWidget);

      await tester.tap(find.text('Ramesh Kumar'));
      await tester.pumpAndSettle();

      // Details sheet
      expect(find.text('+91 90000 11111'), findsOneWidget);
      expect(find.textContaining('Tata Ace'), findsWidgets);
    });

    testWidgets('shows the driver en route once a position arrives', (
      tester,
    ) async {
      await pumpScreen(
        tester,
        _screen(
          view: _view(routeStatus: 'in_progress'),
          driver: DriverPosition(
            point: const LatLng(9.94, 76.27),
            heading: 90,
            at: DateTime.now(),
          ),
        ),
      );

      expect(find.text('Driver en route'), findsOneWidget);
      // destination pin + driver marker
      expect(find.byIcon(Icons.local_shipping), findsWidgets);
    });
  });
}
