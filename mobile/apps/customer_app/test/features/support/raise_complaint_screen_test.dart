import 'package:api_client/api_client.dart';
import 'package:customer_app/src/features/orders/data/orders_provider.dart';
import 'package:customer_app/src/features/support/data/complaints_provider.dart';
import 'package:customer_app/src/features/support/presentation/emergency_contacts_card.dart';
import 'package:customer_app/src/features/support/presentation/raise_complaint_screen.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/pump_screen.dart';

Widget _screen() => ProviderScope(
  overrides: [
    ordersProvider.overrideWith((ref) async => const []),
    supportContactsProvider.overrideWith(
      (ref) async => const SupportContacts(emergencyHelpline: '1906'),
    ),
  ],
  child: MaterialApp(theme: LpgTheme.light, home: const RaiseComplaintScreen()),
);

void main() {
  group('RaiseComplaintScreen', () {
    testWidgets('renders the category, priority and description fields', (
      tester,
    ) async {
      await pumpScreen(tester, _screen());

      expect(find.text('Category'), findsOneWidget);
      expect(find.text('Priority'), findsOneWidget);
      expect(find.text('Submit Complaint'), findsOneWidget);
      // Critical is reserved for safety reports (CA-10).
      expect(find.text('Critical'), findsNothing);
    });

    testWidgets('a gas leak report puts the 1906 helpline first (CA-10)', (
      tester,
    ) async {
      await pumpScreen(tester, _screen());

      await tester.tap(find.text('Other'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Gas leak / safety').last);
      await tester.pumpAndSettle();

      expect(
        find.byKey(EmergencyContactsCard.helplineButtonKey),
        findsOneWidget,
      );
      expect(find.text('Call 1906 (emergency)'), findsOneWidget);
      expect(find.text('Priority'), findsNothing);
    });

    testWidgets('validates that a description is required', (tester) async {
      await pumpScreen(tester, _screen());

      await tester.tap(find.text('Submit Complaint'));
      await tester.pumpAndSettle();

      expect(find.text('Please describe the issue.'), findsOneWidget);
    });
  });
}
