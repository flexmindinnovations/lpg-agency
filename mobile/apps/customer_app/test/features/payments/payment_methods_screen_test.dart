import 'package:customer_app/src/features/payments/presentation/payment_methods_screen.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

Widget _wrap(Widget child) => MaterialApp(theme: LpgTheme.light, home: child);

void main() {
  group('PaymentMethodsScreen', () {
    testWidgets('explains the ways to pay without asking for a card', (
      tester,
    ) async {
      await tester.pumpWidget(_wrap(const PaymentMethodsScreen()));

      expect(find.text('Cash on delivery'), findsOneWidget);
      expect(find.text('UPI or card on delivery'), findsOneWidget);
      expect(find.text('Pay online'), findsOneWidget);
      // CA-16: no "add a card" action that contradicts the copy.
      expect(find.textContaining('Add Credit'), findsNothing);
    });
  });
}
