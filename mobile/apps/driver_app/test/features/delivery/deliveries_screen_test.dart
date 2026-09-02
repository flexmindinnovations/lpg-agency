import 'package:api_client/api_client.dart';
import 'package:design_system/design_system.dart';
import 'package:driver_app/src/features/cash_handover/data/cash_handover_provider.dart';
import 'package:driver_app/src/features/delivery/data/active_route_provider.dart';
import 'package:driver_app/src/features/delivery/presentation/deliveries_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

RouteCashHandover _pendingCash(String routeId) => RouteCashHandover(
  routeId: routeId,
  driverId: 'driver-1',
  routeStatus: 'completed',
  routeDate: DateTime(2026, 8, 30),
  expectedAmount: 500,
  cashStopCount: 1,
);

RouteSummary _route({
  String id = 'route-1',
  String status = 'in_progress',
  DateTime? date,
  List<RouteStopSummary> stops = const [
    RouteStopSummary(
      id: 's1',
      orderId: 'aaaa1111bbbb',
      sequenceNumber: 1,
      status: 'pending',
    ),
  ],
}) => RouteSummary(
  id: id,
  status: status,
  driverId: 'driver-1',
  vehicleId: 'vehicle-1',
  date: date,
  stops: stops,
);

Widget _screen({
  RouteSummary? active,
  List<RouteSummary> history = const [],
  RouteCashHandover? pendingCash,
}) => ProviderScope(
  overrides: [
    activeRouteProvider.overrideWith((ref) async => active),
    routeHistoryProvider.overrideWith((ref) async => history),
    pendingCashHandoverProvider.overrideWith((ref) async => pendingCash),
  ],
  child: MaterialApp(theme: LpgTheme.light, home: const DeliveriesScreen()),
);

void main() {
  group('DeliveriesScreen', () {
    testWidgets('lists the current route\'s stops', (tester) async {
      await tester.pumpWidget(_screen(active: _route()));
      await tester.pumpAndSettle();

      expect(find.text('Current route'), findsOneWidget);
      expect(find.text('Stop 1'), findsOneWidget);
    });

    testWidgets('shows a note when there is no active route', (tester) async {
      await tester.pumpWidget(_screen());
      await tester.pumpAndSettle();

      expect(find.text('No active route right now.'), findsOneWidget);
      expect(find.text('No finished routes yet.'), findsOneWidget);
    });

    testWidgets('renders finished routes under "Past routes"', (tester) async {
      await tester.pumpWidget(
        _screen(
          history: [
            _route(
              id: 'r-old',
              status: 'completed',
              date: DateTime(2026, 8, 30),
              stops: const [
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
                  status: 'delivered',
                ),
              ],
            ),
          ],
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('Past routes'), findsOneWidget);
      expect(find.text('2026-08-30'), findsOneWidget);
      expect(find.textContaining('2 stops'), findsOneWidget);
    });

    testWidgets('flags the past route whose cash still needs declaring', (
      tester,
    ) async {
      await tester.pumpWidget(
        _screen(
          history: [
            _route(id: 'r-old', status: 'completed', date: DateTime(2026, 8, 30)),
            _route(id: 'r-older', status: 'completed', date: DateTime(2026, 8, 25)),
          ],
          pendingCash: _pendingCash('r-old'),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('CASH PENDING'), findsOneWidget);
    });
  });
}
