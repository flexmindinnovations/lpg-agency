import 'package:api_client/api_client.dart';
import 'package:customer_app/src/features/orders/data/order_tracking_provider.dart';
import 'package:customer_app/src/features/orders/data/orders_provider.dart';
import 'package:customer_app/src/features/orders/presentation/order_tracking_screen.dart';
import 'package:customer_app/src/widgets/location_map.dart';
import 'package:customer_app/src/widgets/map_tile_provider.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
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
}) => OrderTrackingView(
  destination: destination,
  destinationLabel: '12 Baker Street',
  destinationIsApproximate: approximate,
  status: 'out_for_delivery',
  routeStatus: routeStatus,
  lastKnownDriverLocation: lastKnown,
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
