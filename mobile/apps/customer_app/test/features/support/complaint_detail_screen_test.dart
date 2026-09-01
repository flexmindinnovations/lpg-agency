import 'package:api_client/api_client.dart';
import 'package:customer_app/src/features/support/data/complaints_provider.dart';
import 'package:customer_app/src/features/support/presentation/complaint_detail_screen.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/pump_screen.dart';

ComplaintResponse _complaint({ComplaintResolutionResponse? resolution}) =>
    ComplaintResponse(
      id: 'cmp-1',
      complaintNumber: 'CMP000007',
      customerId: 'c1',
      category: 'LateDelivery',
      priority: 'High',
      status: resolution == null ? 'Open' : 'Resolved',
      description: 'Cylinder arrived a day late.',
      createdAt: DateTime(2026, 8, 18),
      updatedAt: DateTime(2026, 8, 18),
      resolution: resolution,
    );

Widget _screen({ComplaintResponse? complaint, Object? error}) => ProviderScope(
  overrides: [
    complaintDetailProvider.overrideWith((ref, id) async {
      if (error != null) throw error;
      return complaint ?? _complaint();
    }),
  ],
  child: MaterialApp(
    theme: LpgTheme.light,
    home: const ComplaintDetailScreen(complaintId: 'cmp-1'),
  ),
);

void main() {
  group('ComplaintDetailScreen', () {
    testWidgets('renders the humanized category, description and pending copy', (
      tester,
    ) async {
      await pumpScreen(tester, _screen(complaint: _complaint()));

      expect(find.text('Late Delivery'), findsOneWidget);
      expect(find.text('Cylinder arrived a day late.'), findsOneWidget);
      expect(find.textContaining("We're on it"), findsOneWidget);
    });

    testWidgets('shows the resolution when the complaint is resolved', (
      tester,
    ) async {
      await pumpScreen(
        tester,
        _screen(
          complaint: _complaint(
            resolution: ComplaintResolutionResponse(
              id: 'r1',
              outcome: 'Compensated',
              resolutionNotes: 'Refunded the delivery fee.',
              resolvedBy: 'staff-1',
              resolvedAt: DateTime(2026, 8, 20),
              createdAt: DateTime(2026, 8, 20),
            ),
          ),
        ),
      );

      expect(find.text('Refunded the delivery fee.'), findsOneWidget);
      expect(find.text('COMPENSATED'), findsOneWidget);
    });

    testWidgets('shows an error state with retry when the load fails', (
      tester,
    ) async {
      await pumpScreen(tester, _screen(error: Exception('down')));

      expect(
        find.textContaining('Failed to load this complaint'),
        findsOneWidget,
      );
      expect(find.text('Retry'), findsOneWidget);
    });
  });
}
