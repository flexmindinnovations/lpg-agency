import 'package:design_system/design_system.dart';
import 'package:driver_app/src/features/delivery/data/driver_position_provider.dart';
import 'package:driver_app/src/features/delivery/data/stop_destination_provider.dart';
import 'package:driver_app/src/features/delivery/presentation/widgets/stop_map_card.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:maps/maps.dart';
import 'package:maps/maps_testing.dart';

const _dest = LatLng(17.44, 78.35);

Widget _host({required StopDestination destination, LatLng? driver}) =>
    ProviderScope(
      overrides: [
        stopDestinationProvider.overrideWith((ref, id) async => destination),
        driverPositionProvider.overrideWith((ref) async => driver),
        mapTileProviderProvider.overrideWithValue(FakeTileProvider()),
      ],
      child: MaterialApp(
        theme: LpgTheme.light,
        home: const Scaffold(
          body: SizedBox(
            width: 400,
            height: 500,
            child: StopMapCard(orderId: 'o1'),
          ),
        ),
      ),
    );

void main() {
  group('StopMapCard', () {
    testWidgets('renders the map + a Navigate button for a pinned stop', (
      tester,
    ) async {
      await tester.pumpWidget(
        _host(
          destination: const StopDestination(
            point: _dest,
            label: '12 Baker Street',
            isApproximate: false,
          ),
        ),
      );
      await tester.pump(const Duration(milliseconds: 100));

      expect(find.byType(LocationMap), findsOneWidget);
      expect(find.byType(MarkerLayer), findsOneWidget);
      expect(find.widgetWithText(LpgButton, 'Navigate'), findsOneWidget);
      expect(find.textContaining('Approximate'), findsNothing);
    });

    testWidgets('shows the approximate banner for a geocoded stop', (
      tester,
    ) async {
      await tester.pumpWidget(
        _host(
          destination: const StopDestination(
            point: _dest,
            label: '12 Baker Street',
            isApproximate: true,
          ),
        ),
      );
      await tester.pump(const Duration(milliseconds: 100));

      expect(find.textContaining('Approximate location'), findsOneWidget);
    });

    testWidgets('shows "not pinned" and no Navigate button when unlocated', (
      tester,
    ) async {
      await tester.pumpWidget(
        _host(
          destination: const StopDestination(
            point: null,
            label: '12 Baker Street',
            isApproximate: false,
          ),
        ),
      );
      await tester.pump(const Duration(milliseconds: 100));

      expect(find.text('Delivery location not pinned.'), findsOneWidget);
      expect(find.byType(LocationMap), findsNothing);
      expect(find.widgetWithText(LpgButton, 'Navigate'), findsNothing);
    });
  });
}
