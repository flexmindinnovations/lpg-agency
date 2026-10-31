import 'package:api_client/api_client.dart';
import 'package:dio/dio.dart';
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

    test('parses the balance, customer name and GST split', () async {
      final client = ApiClient(baseUrl: 'https://api.test');
      client.dio.httpClientAdapter = FakeHttpClientAdapter(
        (options) => jsonResponse({
          'invoice_id': 'invoice-1',
          'tenant_id': 'tenant-1',
          'customer_id': 'customer-1',
          'order_id': 'order-1',
          'status': 'partially_paid',
          'issued_at': '2026-08-01T00:00:00Z',
          'lines': <Map<String, dynamic>>[],
          'subtotal': 905.5,
          'tax_amount': 45.28,
          'total_amount': 950.78,
          'version': 2,
          'amount_paid': 905.5,
          'balance_due': '45.28',
          'customer_name': 'E2E Customer',
          'customer_gstin': '36ABCDE1234F1Z5',
          'is_inter_state': false,
          'cgst_amount': '22.64',
          'sgst_amount': '22.64',
          'igst_amount': '0',
        }, 200),
      );

      final result = await InvoiceApi(client.dio).getInvoice('invoice-1');

      final invoice = result.when(onSuccess: (i) => i, onFailure: (_) => null)!;
      expect(invoice.balanceDue, 45.28);
      expect(invoice.customerName, 'E2E Customer');
      expect(invoice.cgstAmount, 22.64);
      expect(invoice.isInterState, isFalse);
      expect(invoice.isSettled, isFalse);
    });

    test('recordPayment posts the method, amount and reference', () async {
      RequestOptions? seen;
      final client = ApiClient(baseUrl: 'https://api.test');
      client.dio.httpClientAdapter = FakeHttpClientAdapter((options) {
        seen = options;
        return jsonResponse({
          'invoice_id': 'invoice-1',
          'tenant_id': 'tenant-1',
          'customer_id': 'customer-1',
          'order_id': 'order-1',
          'status': 'paid',
          'issued_at': '2026-08-01T00:00:00Z',
          'lines': <Map<String, dynamic>>[],
          'subtotal': 900.0,
          'tax_amount': 0.0,
          'total_amount': 900.0,
          'version': 3,
          'amount_paid': 900.0,
          'balance_due': '0',
        }, 201);
      });

      final result = await InvoiceApi(client.dio).recordPayment(
        'invoice-1',
        method: 'upi',
        amount: 900,
        reference: 'UTR123',
      );

      expect(seen!.method, 'POST');
      expect(seen!.path, '/api/v1/invoices/invoice-1/payments');
      expect(seen!.data, {
        'method': 'upi',
        'amount': '900.00',
        'reference': 'UTR123',
      });
      expect(
        result.when(onSuccess: (i) => i.isSettled, onFailure: (_) => false),
        isTrue,
      );
    });

    test('getMyInvoices narrows by customer and search', () async {
      RequestOptions? seen;
      final client = ApiClient(baseUrl: 'https://api.test');
      client.dio.httpClientAdapter = FakeHttpClientAdapter((options) {
        seen = options;
        return jsonResponse({
          'items': <Map<String, dynamic>>[],
          'total': 0,
          'page': 1,
          'page_size': 50,
        }, 200);
      });

      await InvoiceApi(client.dio).getMyInvoices(
        customerId: 'customer-1',
        search: 'INV-9',
        status: 'issued',
      );

      expect(seen!.queryParameters['customer_id'], 'customer-1');
      expect(seen!.queryParameters['search'], 'INV-9');
      expect(seen!.queryParameters['status'], 'issued');
    });
  });
  group('InvoiceApi by order', () {
    test('getMyInvoices can be limited to one order', () async {
      final client = ApiClient(baseUrl: 'https://api.test');
      client.dio.httpClientAdapter = FakeHttpClientAdapter((options) {
        expect(options.queryParameters['order_id'], 'o-1');
        return jsonResponse({
          'items': <Object>[],
          'total': 0,
          'page': 1,
          'page_size': 50,
        }, 200);
      });

      final result = await InvoiceApi(client.dio).getMyInvoices(orderId: 'o-1');

      expect(
        result.when(onSuccess: (_) => true, onFailure: (_) => false),
        isTrue,
      );
    });
  });
}
