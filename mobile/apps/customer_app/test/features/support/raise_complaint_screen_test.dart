import 'package:customer_app/src/features/orders/data/orders_provider.dart';
import 'package:customer_app/src/features/support/presentation/raise_complaint_screen.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/pump_screen.dart';

Widget _screen() => ProviderScope(
  overrides: [ordersProvider.overrideWith((ref) async => const [])],
  child: MaterialApp(theme: LpgTheme.light, home: const RaiseComplaintScreen()),
);

void main() {
  group('RaiseComplaintScreen', () {
    testWidgets('renders the category, priority and description fields', (
      tester,
    ) async {
      await pumpScreen(tester, _screen());

      expect(find.text('CATEGORY'), findsOneWidget);
      expect(find.text('PRIORITY'), findsOneWidget);
      expect(find.text('Submit Complaint'), findsOneWidget);
    });

    testWidgets('validates that a description is required', (tester) async {
      await pumpScreen(tester, _screen());

      await tester.tap(find.text('Submit Complaint'));
      await tester.pumpAndSettle();

      expect(find.text('Please describe the issue.'), findsOneWidget);
    });
  });
}
