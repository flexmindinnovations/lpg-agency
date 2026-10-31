import 'package:admin_app/src/features/invoices/presentation/record_payment_sheet.dart';
import 'package:admin_app/src/providers.dart';
import 'package:admin_app/src/shared/invoice_tile.dart';
import 'package:api_client/api_client.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

InvoiceResponse _invoice({
  String status = 'partially_paid',
  double total = 950.78,
  double due = 45.28,
}) => InvoiceResponse(
  invoiceId: 'inv-1',
  invoiceNumber: 'INV-2026-000013',
  tenantId: 't1',
  customerId: 'c1',
  orderId: 'o1',
  status: status,
  issuedAt: DateTime(2026, 10, 29),
  lines: const [],
  subtotal: 905.5,
  taxAmount: 45.28,
  totalAmount: total,
  version: 1,
  amountPaid: total - due,
  balanceDue: due,
  customerName: 'E2E Customer',
);

Widget _host(Widget child) => ProviderScope(
  overrides: [
    // Validation must stop before any request; reaching the API fails the test.
    invoiceApiProvider.overrideWith(
      (ref) => throw StateError('the API must not be called'),
    ),
    // An agency with a UPI ID and bank details on its payment profile.
    paymentMethodsProvider.overrideWith(
      (ref) async => const PaymentMethods(
        booking: [],
        delivery: [],
        office: [
          PaymentMethodOption(code: 'cash', label: 'Cash'),
          PaymentMethodOption(code: 'upi', label: 'UPI'),
          PaymentMethodOption(code: 'cheque', label: 'Cheque'),
          PaymentMethodOption(code: 'bank_transfer', label: 'Bank transfer'),
        ],
      ),
    ),
  ],
  child: MaterialApp(
    theme: LpgTheme.light,
    home: Scaffold(body: child),
  ),
);

void main() {
  group('InvoiceTile', () {
    testWidgets('shows the number, customer, status, total and what is due', (
      tester,
    ) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: LpgTheme.light,
          home: Scaffold(
            body: InvoiceTile(
              invoice: _invoice(),
              showCustomer: true,
              onTap: () {},
            ),
          ),
        ),
      );

      expect(find.text('INV-2026-000013'), findsOneWidget);
      expect(find.textContaining('E2E Customer'), findsOneWidget);
      expect(find.textContaining('Partially paid'), findsOneWidget);
      expect(find.text('₹950.78'), findsOneWidget);
      expect(find.textContaining('45.28 due'), findsOneWidget);
    });

    testWidgets('a paid invoice shows no amount due', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: LpgTheme.light,
          home: Scaffold(
            body: InvoiceTile(
              invoice: _invoice(status: 'paid', due: 0),
              onTap: () {},
            ),
          ),
        ),
      );

      expect(find.textContaining('due'), findsNothing);
    });
  });

  group('invoiceStatusSeverity', () {
    test('reads paid as success and part paid as a warning', () {
      expect(invoiceStatusSeverity('paid'), LpgStatusSeverity.success);
      expect(
        invoiceStatusSeverity('partially_paid'),
        LpgStatusSeverity.warning,
      );
      expect(invoiceStatusSeverity('cancelled'), LpgStatusSeverity.danger);
    });
  });

  group('RecordPaymentSheet', () {
    testWidgets('starts at the balance due', (tester) async {
      await tester.pumpWidget(_host(RecordPaymentSheet(invoice: _invoice())));

      expect(find.widgetWithText(TextField, '45.28'), findsOneWidget);
    });

    testWidgets('offers only the ways of paying the agency has set up', (
      tester,
    ) async {
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            paymentMethodsProvider.overrideWith(
              (ref) async => const PaymentMethods(
                booking: [],
                delivery: [],
                office: [
                  PaymentMethodOption(code: 'cash', label: 'Cash'),
                  PaymentMethodOption(code: 'cheque', label: 'Cheque'),
                ],
              ),
            ),
          ],
          child: MaterialApp(
            theme: LpgTheme.light,
            home: Scaffold(body: RecordPaymentSheet(invoice: _invoice())),
          ),
        ),
      );
      await tester.pumpAndSettle();

      await tester.tap(find.text('Cash'));
      await tester.pumpAndSettle();

      expect(find.text('Cheque'), findsWidgets);
      expect(find.text('UPI'), findsNothing);
      expect(find.text('Bank transfer'), findsNothing);
      expect(find.text('Card'), findsNothing);
    });

    testWidgets('refuses more than the balance without calling the API', (
      tester,
    ) async {
      await tester.pumpWidget(_host(RecordPaymentSheet(invoice: _invoice())));

      await tester.enterText(find.byType(TextField).first, '500');
      await tester.tap(find.text('Save payment'));
      await tester.pump();

      expect(find.textContaining('more than the'), findsOneWidget);
    });

    testWidgets('a cheque needs its number before it can be saved', (
      tester,
    ) async {
      await tester.pumpWidget(_host(RecordPaymentSheet(invoice: _invoice())));
      await tester.pumpAndSettle(); // the agency's payment methods arrive

      await tester.tap(find.text('Cash').first);
      await tester.pumpAndSettle();
      await tester.tap(find.text('Cheque'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Save payment'));
      await tester.pump();

      expect(find.textContaining('cheque number'), findsOneWidget);
    });
  });
}
