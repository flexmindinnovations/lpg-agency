import 'package:api_client/api_client.dart';
import 'package:customer_app/src/features/support/data/complaints_provider.dart';
import 'package:customer_app/src/features/support/presentation/support_screen.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/pump_screen.dart';

ComplaintResponse _complaint({String status = 'Open'}) => ComplaintResponse(
  id: 'cmp-1',
  complaintNumber: 'CMP000007',
  customerId: 'c1',
  category: 'LateDelivery',
  priority: 'High',
  status: status,
  description: 'Cylinder arrived a day late.',
  createdAt: DateTime(2026, 8, 18),
  updatedAt: DateTime(2026, 8, 18),
);

Widget _screen({List<ComplaintResponse>? complaints, Object? error}) =>
    ProviderScope(
      overrides: [
        complaintsProvider.overrideWith((ref) async {
          if (error != null) throw error;
          return complaints ?? const [];
        }),
      ],
      child: MaterialApp(theme: LpgTheme.light, home: const SupportScreen()),
    );

void main() {
  group('SupportScreen', () {
    testWidgets('always offers the "Raise a Complaint" action', (tester) async {
      await pumpScreen(tester, _screen(complaints: const []));

      expect(find.text('Raise a Complaint'), findsOneWidget);
      expect(find.text('No complaints raised yet.'), findsOneWidget);
    });

    testWidgets('lists an existing ticket with its category and status', (
      tester,
    ) async {
      await pumpScreen(tester, _screen(complaints: [_complaint()]));

      expect(find.text('LateDelivery'), findsOneWidget);
      expect(find.text('OPEN'), findsOneWidget);
    });

    testWidgets('shows an error state with retry when the load fails', (
      tester,
    ) async {
      await pumpScreen(tester, _screen(error: Exception('down')));

      expect(find.textContaining('Failed to load tickets'), findsOneWidget);
      expect(find.text('Retry'), findsOneWidget);
    });
  });
}
