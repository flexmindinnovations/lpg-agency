import 'package:api_client/api_client.dart';
import 'package:customer_app/src/features/orders/data/invoices_provider.dart';
import 'package:customer_app/src/features/orders/presentation/invoice_list_screen.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/pump_screen.dart';

InvoiceResponse _invoice({String status = 'issued', String? number = '000042'}) =>
    InvoiceResponse(
      invoiceId: 'inv-abcd1234',
      invoiceNumber: number,
      tenantId: 't1',
      customerId: 'c1',
      orderId: 'o1',
      status: status,
      issuedAt: DateTime(2026, 8, 15),
      lines: const [],
      subtotal: 1000,
      taxAmount: 180,
      totalAmount: 1180,
      version: 1,
    );

Widget _screen({List<InvoiceResponse>? invoices, Object? error}) => ProviderScope(
  overrides: [
    invoicesProvider.overrideWith((ref) async {
      if (error != null) throw error;
      return invoices ?? const [];
    }),
  ],
  child: MaterialApp(theme: LpgTheme.light, home: const InvoiceListScreen()),
);

void main() {
  group('InvoiceListScreen', () {
    testWidgets('shows the empty state', (tester) async {
      await pumpScreen(tester, _screen(invoices: const []));

      expect(find.text('No invoices found.'), findsOneWidget);
    });

    testWidgets('renders an invoice with its number, status and amount', (
      tester,
    ) async {
      await pumpScreen(tester, _screen(invoices: [_invoice()]));

      expect(find.textContaining('000042'), findsOneWidget);
      expect(find.text('ISSUED'), findsOneWidget);
      expect(find.textContaining('1180.00'), findsOneWidget);
    });

    testWidgets('shows an error state with retry when the load fails', (
      tester,
    ) async {
      await pumpScreen(tester, _screen(error: Exception('down')));

      expect(find.textContaining('Failed to load invoices'), findsOneWidget);
      expect(find.text('Retry'), findsOneWidget);
    });
  });
}
