import 'package:api_client/api_client.dart';
import 'package:design_system/design_system.dart';
import 'package:driver_app/src/features/delivery/data/active_route_provider.dart';
import 'package:driver_app/src/features/delivery/data/location_sharing.dart';
import 'package:driver_app/src/features/delivery/presentation/active_delivery_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

RouteSummary _route({String status = 'in_progress'}) => RouteSummary(
  id: 'route-1',
  status: status,
  driverId: 'driver-1',
  vehicleId: 'vehicle-1',
  stops: const [
    RouteStopSummary(
      id: 'stop-1',
      orderId: 'abcdef12aaaa',
      sequenceNumber: 0,
      status: 'pending',
    ),
  ],
);

/// `LocationSharingController` isn't `final`, so a subclass can stand in and
/// record the screen's start/stop calls without any platform channels.
class _FakeController extends LocationSharingController {
  _FakeController()
    : super(
        routeApi: RouteApi(ApiClient(baseUrl: 'https://test').dio),
        geolocator: const DriverGeolocator(),
      );

  final calls = <String>[];

  @override
  Future<void> start(String routeId) async => calls.add('start:$routeId');

  @override
  void stop() => calls.add('stop');
}

Widget _screen({
  RouteSummary? route,
  LocationSharingState state = const LocationSharingState(),
  required _FakeController controller,
}) => ProviderScope(
  overrides: [
    activeRouteProvider.overrideWith((ref) async => route ?? _route()),
    locationSharingControllerProvider.overrideWithValue(controller),
    locationSharingStateProvider.overrideWith((ref) => Stream.value(state)),
  ],
  child: MaterialApp(
    theme: LpgTheme.light,
    home: const ActiveDeliveryScreen(),
  ),
);

void main() {
  group('ActiveDeliveryScreen', () {
    testWidgets('renders the route status and its stops', (tester) async {
      await tester.pumpWidget(_screen(controller: _FakeController()));
      await tester.pumpAndSettle();

      expect(find.text('IN PROGRESS'), findsOneWidget);
      expect(find.text('Stop 1'), findsOneWidget);
      expect(find.text('Share live location'), findsOneWidget);
    });

    testWidgets('the sharing switch starts sharing on an in-progress route', (
      tester,
    ) async {
      final controller = _FakeController();
      await tester.pumpWidget(_screen(controller: controller));
      await tester.pumpAndSettle();

      await tester.tap(find.byType(Switch));
      await tester.pump();

      expect(controller.calls, ['start:route-1']);
    });

    testWidgets('the sharing switch is disabled before the route departs', (
      tester,
    ) async {
      final controller = _FakeController();
      await tester.pumpWidget(
        _screen(route: _route(status: 'loaded'), controller: controller),
      );
      await tester.pumpAndSettle();

      final toggle = tester.widget<Switch>(find.byType(Switch));
      expect(toggle.onChanged, isNull);
      expect(find.textContaining('once you depart'), findsOneWidget);
    });

    testWidgets('turning the switch off stops sharing', (tester) async {
      final controller = _FakeController();
      await tester.pumpWidget(
        _screen(
          controller: controller,
          state: const LocationSharingState(
            status: LocationSharingStatus.sharing,
          ),
        ),
      );
      await tester.pumpAndSettle();

      await tester.tap(find.byType(Switch));
      await tester.pump();

      expect(controller.calls, ['stop']);
    });
  });
}
