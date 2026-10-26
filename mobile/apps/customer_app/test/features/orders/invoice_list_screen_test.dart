import 'package:api_client/api_client.dart';
import 'package:customer_app/src/features/orders/data/invoices_provider.dart';
import 'package:customer_app/src/features/orders/presentation/invoice_list_screen.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';

import '../../support/pump_screen.dart';

InvoiceResponse _invoice({
  String status = 'issued',
  String? number = '000042',
}) => InvoiceResponse(
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

Widget _screen({List<InvoiceResponse>? invoices, Object? error}) =>
    ProviderScope(
      overrides: [
        invoicesProvider.overrideWith((ref) async {
          if (error != null) throw error;
          return invoices ?? const [];
        }),
      ],
      child: MaterialApp(
        theme: LpgTheme.light,
        home: const InvoiceListScreen(),
      ),
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
      expect(find.text('Issued'), findsOneWidget);
      expect(find.textContaining('1,180.00'), findsOneWidget);
    });

    testWidgets('tapping anywhere on the card opens the invoice (CA-15)', (
      tester,
    ) async {
      String? opened;
      await pumpScreen(
        tester,
        ProviderScope(
          overrides: [
            invoicesProvider.overrideWith((ref) async => [_invoice()]),
          ],
          child: MaterialApp.router(
            theme: LpgTheme.light,
            routerConfig: GoRouter(
              routes: [
                GoRoute(
                  path: '/',
                  builder: (_, _) => const InvoiceListScreen(),
                ),
                GoRoute(
                  path: '/orders/invoices/:id',
                  builder: (_, state) {
                    opened = state.pathParameters['id'];
                    return const Text('detail');
                  },
                ),
              ],
            ),
          ),
        ),
      );

      // The middle of the card, not the "View" label.
      await tester.tap(find.text('Issued'));
      await tester.pumpAndSettle();
      expect(opened, 'inv-abcd1234');
    });

    testWidgets(
      "doesn't double-prefix an invoice number that already has its own "
      '"INV-..." prefix',
      (tester) async {
        await pumpScreen(
          tester,
          _screen(invoices: [_invoice(number: 'INV-2026-000011')]),
        );

        expect(find.text('INV-2026-000011'), findsOneWidget);
        expect(find.text('INV-INV-2026-000011'), findsNothing);
      },
    );

    testWidgets('shows an error state with retry when the load fails', (
      tester,
    ) async {
      await pumpScreen(tester, _screen(error: Exception('down')));

      expect(find.textContaining('Failed to load invoices'), findsOneWidget);
      expect(find.text('Retry'), findsOneWidget);
    });
  });
}
