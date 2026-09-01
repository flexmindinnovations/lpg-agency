import 'package:api_client/api_client.dart';
import 'package:customer_app/src/features/orders/data/cylinder_types_provider.dart';
import 'package:customer_app/src/features/orders/data/invoices_provider.dart';
import 'package:customer_app/src/features/orders/presentation/invoice_detail_screen.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/pump_screen.dart';

InvoiceResponse _invoice({String status = 'partially_paid'}) => InvoiceResponse(
  invoiceId: 'inv-abcd1234',
  invoiceNumber: '000042',
  tenantId: 't1',
  customerId: 'c1',
  orderId: 'o1',
  status: status,
  issuedAt: DateTime(2026, 8, 15),
  lines: const [
    InvoiceLineResponse(
      lineId: 'l1',
      cylinderTypeId: 'ct1',
      quantity: 2,
      unitPrice: 500,
      subtotal: 1000,
      taxAmount: 180,
      totalAmount: 1180,
    ),
  ],
  subtotal: 1000,
  taxAmount: 180,
  totalAmount: 1180,
  version: 1,
  amountPaid: 500,
);

Widget _screen({bool nullInvoice = false, Object? error}) => ProviderScope(
  overrides: [
    invoiceDetailProvider.overrideWith((ref, id) async {
      if (error != null) throw error;
      return nullInvoice ? null : _invoice();
    }),
    cylinderTypesProvider.overrideWith((ref) async => const []),
  ],
  child: MaterialApp(
    theme: LpgTheme.light,
    home: const InvoiceDetailScreen(invoiceId: 'inv-abcd1234'),
  ),
);

void main() {
  group('InvoiceDetailScreen', () {
    testWidgets('renders the invoice status', (tester) async {
      await pumpScreen(tester, _screen());

      expect(find.text('Invoice Details'), findsOneWidget);
      expect(find.textContaining('PARTIALLY'), findsWidgets);
    });

    testWidgets('shows a not-found state when the invoice is null', (
      tester,
    ) async {
      await pumpScreen(tester, _screen(nullInvoice: true));

      expect(find.text('This invoice could not be found.'), findsOneWidget);
    });

    testWidgets('shows an error state with retry when the load fails', (
      tester,
    ) async {
      await pumpScreen(tester, _screen(error: Exception('down')));

      expect(find.textContaining('Failed to load this invoice'), findsOneWidget);
      expect(find.text('Retry'), findsOneWidget);
    });
  });
}
