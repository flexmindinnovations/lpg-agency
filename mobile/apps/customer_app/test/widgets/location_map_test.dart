import 'package:customer_app/src/widgets/location_map.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:latlong2/latlong.dart';

import '../support/fake_tiles.dart';

const _kochi = LatLng(9.9312, 76.2673);

Widget _host(Widget child) => MaterialApp(
  theme: LpgTheme.light,
  home: Scaffold(body: SizedBox(width: 400, height: 400, child: child)),
);

void main() {
  group('LocationMap', () {
    testWidgets('renders a FlutterMap with the given marker', (tester) async {
      await tester.pumpWidget(
        _host(
          LocationMap(
            center: _kochi,
            tileProvider: FakeTileProvider(),
            markers: [pinMarker(point: _kochi, color: Colors.red)],
          ),
        ),
      );
      await tester.pump(const Duration(milliseconds: 100));

      expect(find.byType(FlutterMap), findsOneWidget);
      expect(find.byType(MarkerLayer), findsOneWidget);
    });

    testWidgets('is non-interactive by default', (tester) async {
      await tester.pumpWidget(
        _host(LocationMap(center: _kochi, tileProvider: FakeTileProvider())),
      );
      await tester.pump(const Duration(milliseconds: 100));

      final map = tester.widget<FlutterMap>(find.byType(FlutterMap));
      expect(map.options.interactionOptions.flags, InteractiveFlag.none);
    });
  });

  group('MapUnavailable', () {
    testWidgets('shows the message', (tester) async {
      await tester.pumpWidget(
        _host(const MapUnavailable(message: 'No location pinned.')),
      );

      expect(find.text('No location pinned.'), findsOneWidget);
    });
  });
}
