import 'package:api_client/api_client.dart';
import 'package:customer_app/src/features/orders/presentation/invoice_pdf.dart';
import 'package:customer_app/src/i18n/customer_strings.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('builds a non-empty PDF with the rupee font bundled', () async {
    final invoice = InvoiceResponse(
      invoiceId: 'inv-abcd1234',
      invoiceNumber: 'INV-1',
      tenantId: 't1',
      customerId: 'c1',
      orderId: 'o1',
      status: 'paid',
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
      amountPaid: 1180,
    );
    final bytes = await buildInvoicePdf(
      invoice,
      cylinderNames: const {'ct1': '14.2 kg'},
      s: customerStringsFor(const Locale('en')),
    );
    expect(String.fromCharCodes(bytes.take(4)), '%PDF');
    expect(bytes.length, greaterThan(5000));
  });
}
