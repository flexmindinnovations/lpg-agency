import 'package:api_client/api_client.dart';
import 'package:design_system/design_system.dart';
import 'package:driver_app/src/features/cash_handover/data/cash_handover_provider.dart';
import 'package:driver_app/src/features/delivery/data/active_route_provider.dart';
import 'package:driver_app/src/features/delivery/data/location_sharing.dart';
import 'package:driver_app/src/features/delivery/presentation/today_screen.dart';
import 'package:driver_app/src/features/van_load/data/van_load_provider.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

RouteCashHandover _cashView() => RouteCashHandover(
  routeId: 'route-9',
  driverId: 'driver-1',
  routeStatus: 'completed',
  routeDate: DateTime(2026, 8, 30),
  expectedAmount: 1200,
  cashStopCount: 2,
);

RouteSummary _route({
  String status = 'in_progress',
  List<RouteStopSummary> stops = const [
    RouteStopSummary(
      id: 's1',
      orderId: 'aaaa1111bbbb',
      sequenceNumber: 1,
      status: 'delivered',
    ),
    RouteStopSummary(
      id: 's2',
      orderId: 'cccc2222dddd',
      sequenceNumber: 2,
      status: 'pending',
    ),
  ],
}) => RouteSummary(
  id: 'route-1',
  status: status,
  driverId: 'driver-1',
  vehicleId: 'vehicle-1',
  stops: stops,
);

class _FakeController extends LocationSharingController {
  _FakeController()
    : super(
        routeApi: RouteApi(ApiClient(baseUrl: 'https://test').dio),
        geolocator: const DriverGeolocator(),
      );

  @override
  Future<void> start(String routeId) async {}

  @override
  void stop() {}
}

Widget _screen({
  RouteSummary? route,
  RouteCashHandover? pendingCash,
  RouteSummary? pendingLoad,
}) => ProviderScope(
  overrides: [
    activeRouteProvider.overrideWith((ref) async => route),
    pendingCashHandoverProvider.overrideWith((ref) async => pendingCash),
    pendingLoadProvider.overrideWith((ref) async => pendingLoad),
    locationSharingControllerProvider.overrideWithValue(_FakeController()),
    locationSharingStateProvider.overrideWith(
      (ref) => Stream.value(const LocationSharingState()),
    ),
  ],
  child: MaterialApp(theme: LpgTheme.light, home: const TodayScreen()),
);

void main() {
  group('TodayScreen', () {
    testWidgets('shows an empty state when there is no route', (tester) async {
      await tester.pumpWidget(_screen());
      await tester.pumpAndSettle();

      expect(find.text('No route assigned yet.'), findsOneWidget);
    });

    testWidgets('summarises progress and the next stop', (tester) async {
      await tester.pumpWidget(_screen(route: _route()));
      await tester.pumpAndSettle();

      expect(find.text('1 of 2 delivered'), findsOneWidget);
      expect(find.textContaining('Next stop · Stop 2'), findsOneWidget);
      expect(find.text('Share live location'), findsOneWidget);
    });

    testWidgets('nudges the driver when a route needs cash reconciled', (
      tester,
    ) async {
      await tester.pumpWidget(_screen(pendingCash: _cashView()));
      await tester.pumpAndSettle();

      expect(find.text('Cash reconciliation pending'), findsOneWidget);
      expect(find.textContaining('Declare ₹1200.00'), findsOneWidget);
    });

    testWidgets('nudges the driver to check the van load', (tester) async {
      await tester.pumpWidget(
        _screen(
          route: _route(status: 'loaded'),
          pendingLoad: _route(status: 'loaded'),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('Check your van load'), findsOneWidget);
    });

    testWidgets('reports when every stop is done', (tester) async {
      await tester.pumpWidget(
        _screen(
          route: _route(
            stops: const [
              RouteStopSummary(
                id: 's1',
                orderId: 'aaaa1111bbbb',
                sequenceNumber: 1,
                status: 'delivered',
              ),
            ],
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.textContaining('All stops done'), findsOneWidget);
    });
  });
}
