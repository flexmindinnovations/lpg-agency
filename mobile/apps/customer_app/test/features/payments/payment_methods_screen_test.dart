import 'package:customer_app/src/features/payments/presentation/payment_methods_screen.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

Widget _wrap(Widget child) =>
    MaterialApp(theme: LpgTheme.light, home: child);

void main() {
  group('PaymentMethodsScreen', () {
    testWidgets('shows the empty state and both add actions', (tester) async {
      await tester.pumpWidget(_wrap(const PaymentMethodsScreen()));

      expect(find.textContaining('No payment methods saved yet'), findsOneWidget);
      expect(find.text('Add Credit / Debit Card'), findsOneWidget);
      expect(find.text('Add UPI ID'), findsOneWidget);
    });

    testWidgets('an add action explains the feature is not live yet', (
      tester,
    ) async {
      await tester.pumpWidget(_wrap(const PaymentMethodsScreen()));

      await tester.tap(find.text('Add UPI ID'));
      await tester.pumpAndSettle();

      expect(find.text('UPI payments are coming soon'), findsOneWidget);
      // The sheet dismisses without persisting anything.
      await tester.tap(find.text('Got it'));
      await tester.pumpAndSettle();
      expect(find.text('UPI payments are coming soon'), findsNothing);
      expect(find.textContaining('No payment methods saved yet'), findsOneWidget);
    });
  });
}
