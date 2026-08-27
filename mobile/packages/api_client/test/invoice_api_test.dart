import 'package:api_client/api_client.dart';
import 'package:flutter_test/flutter_test.dart';

import 'support/fake_http_client_adapter.dart';

void main() {
  group('InvoiceApi', () {
    test('getMyInvoices parses the page/pageSize pagination shape', () async {
      final client = ApiClient(baseUrl: 'https://api.test');
      client.dio.httpClientAdapter = FakeHttpClientAdapter(
        (options) => jsonResponse({
          'items': [
            {
              'invoice_id': 'invoice-1',
              'invoice_number': 'INV-0001',
              'tenant_id': 'tenant-1',
              'customer_id': 'customer-1',
              'order_id': 'order-1',
              'status': 'issued',
              'issued_at': '2026-08-01T00:00:00Z',
              'lines': <Map<String, dynamic>>[],
              'subtotal': 900.0,
              'tax_amount': 5.5,
              'total_amount': 905.5,
              'version': 1,
            },
          ],
          'total': 1,
          'page': 1,
          'page_size': 50,
        }, 200),
      );
      final invoiceApi = InvoiceApi(client.dio);

      final result = await invoiceApi.getMyInvoices();

      final page = result.when(onSuccess: (p) => p, onFailure: (_) => null);
      expect(page, isNotNull);
      expect(page!.total, 1);
      expect(page.page, 1);
      expect(page.items.single.invoiceId, 'invoice-1');
      expect(page.items.single.amountPaid, 0, reason: 'defaults when absent');
      expect(page.items.single.payments, isEmpty);
    });

    test('getInvoice parses payments when present', () async {
      final client = ApiClient(baseUrl: 'https://api.test');
      client.dio.httpClientAdapter = FakeHttpClientAdapter(
        (options) => jsonResponse({
          'invoice_id': 'invoice-1',
          'tenant_id': 'tenant-1',
          'customer_id': 'customer-1',
          'order_id': 'order-1',
          'status': 'paid',
          'issued_at': '2026-08-01T00:00:00Z',
          'lines': <Map<String, dynamic>>[],
          'subtotal': 900.0,
          'tax_amount': 5.5,
          'total_amount': 905.5,
          'version': 2,
          'payments': [
            {
              'payment_id': 'payment-1',
              'method': 'cash',
              'amount': 905.5,
              'collected_by': 'driver-1',
              'collected_at': '2026-08-02T00:00:00Z',
            },
          ],
          'amount_paid': 905.5,
        }, 200),
      );
      final invoiceApi = InvoiceApi(client.dio);

      final result = await invoiceApi.getInvoice('invoice-1');

      final invoice = result.when(onSuccess: (i) => i, onFailure: (_) => null);
      expect(invoice, isNotNull);
      expect(invoice!.payments, hasLength(1));
      expect(invoice.amountPaid, 905.5);
    });
  });
}
