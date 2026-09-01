import 'package:customer_app/src/widgets/location_map.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:latlong2/latlong.dart';

import '../support/fake_tiles.dart';

const _kochi = LatLng(9.9312, 76.2673);

List<String> _attributionTexts(WidgetTester tester) {
  final widget = tester.widget<RichAttributionWidget>(
    find.byType(RichAttributionWidget),
  );
  return widget.attributions
      .whereType<TextSourceAttribution>()
      .map((a) => a.text)
      .toList();
}

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

    testWidgets('uses LocationIQ street tiles when an API key is configured', (
      tester,
    ) async {
      await tester.pumpWidget(
        _host(
          LocationMap(
            center: _kochi,
            tileProvider: FakeTileProvider(),
            tileApiKey: 'pk.test-key',
          ),
        ),
      );
      await tester.pump(const Duration(milliseconds: 100));

      final tiles = tester.widget<TileLayer>(find.byType(TileLayer));
      expect(tiles.urlTemplate, contains('tiles.locationiq.com/v3/streets'));
      expect(tiles.urlTemplate, contains('key=pk.test-key'));
      expect(_attributionTexts(tester), contains('© LocationIQ'));
    });

    testWidgets('falls back to OSM tiles without a key, and never shows the '
        'flutter_map promo', (tester) async {
      await tester.pumpWidget(
        _host(
          LocationMap(
            center: _kochi,
            tileProvider: FakeTileProvider(),
            tileApiKey: '',
          ),
        ),
      );
      await tester.pump(const Duration(milliseconds: 100));

      final tiles = tester.widget<TileLayer>(find.byType(TileLayer));
      expect(tiles.urlTemplate, 'https://tile.openstreetmap.org/{z}/{x}/{y}.png');

      final attribution = tester.widget<RichAttributionWidget>(
        find.byType(RichAttributionWidget),
      );
      expect(attribution.showFlutterMapAttribution, isFalse);
      expect(_attributionTexts(tester), isNot(contains('© LocationIQ')));
      expect(
        _attributionTexts(tester),
        contains('© OpenStreetMap contributors'),
      );
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
