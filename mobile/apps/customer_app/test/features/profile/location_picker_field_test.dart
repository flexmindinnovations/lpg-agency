import 'package:customer_app/src/features/profile/presentation/widgets/location_picker_field.dart';
import 'package:customer_app/src/widgets/location_map.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:latlong2/latlong.dart';

import '../../support/fake_tiles.dart';

Widget _host(Widget child) => MaterialApp(
  theme: LpgTheme.light,
  home: Scaffold(body: Padding(padding: const EdgeInsets.all(16), child: child)),
);

void main() {
  group('LocationPickerField', () {
    testWidgets('with no value shows the "pin location" call to action', (
      tester,
    ) async {
      await tester.pumpWidget(
        _host(LocationPickerField(value: null, onChanged: (_) {})),
      );

      expect(find.text('Pin location on map (optional)'), findsOneWidget);
      expect(find.byType(LocationMap), findsNothing);
    });

    testWidgets('with a value shows a map preview and Change / Remove', (
      tester,
    ) async {
      var changes = 0;
      LatLng? lastValue = const LatLng(9.9312, 76.2673);
      await tester.pumpWidget(
        _host(
          LocationPickerField(
            value: const LatLng(9.9312, 76.2673),
            tileProvider: FakeTileProvider(),
            onChanged: (v) {
              changes++;
              lastValue = v;
            },
          ),
        ),
      );
      await tester.pump(const Duration(milliseconds: 100));

      expect(find.byType(LocationMap), findsOneWidget);
      expect(find.text('Location pinned'), findsOneWidget);

      await tester.tap(find.text('Remove'));
      expect(changes, 1);
      expect(lastValue, isNull);
    });
  });
}
