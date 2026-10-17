import 'package:api_client/api_client.dart';
import 'package:flutter_test/flutter_test.dart';

import 'support/fake_http_client_adapter.dart';

Map<String, dynamic> _payment({String status = 'created'}) => {
  'online_payment_id': 'pay-1',
  'order_id': 'order-1',
  'invoice_id': null,
  'amount': '945.00',
  'currency': 'INR',
  'status': status,
  'provider': 'razorpay',
  'payment_url': 'https://rzp.io/i/abc',
  'expires_at': '2026-10-18T12:00:00Z',
  'paid_at': status == 'paid' ? '2026-10-17T12:05:00Z' : null,
  'payment_method': status == 'paid' ? 'upi' : null,
  'applied_to_invoice': false,
  'created_at': '2026-10-17T12:00:00Z',
};

void main() {
  group('PaymentApi', () {
    test(
      'createPaymentLink posts to the order and parses Decimal strings',
      () async {
        String? path;
        String? method;
        final client = ApiClient(baseUrl: 'https://api.test');
        client.dio.httpClientAdapter = FakeHttpClientAdapter((options) {
          path = options.path;
          method = options.method;
          return jsonResponse(_payment(), 201);
        });

        final result = await PaymentApi(
          client.dio,
        ).createPaymentLink('order-1');

        final payment = result.when(
          onSuccess: (p) => p,
          onFailure: (_) => null,
        );
        expect(method, 'POST');
        expect(path, '/api/v1/orders/order-1/payment-links');
        expect(payment!.amount, 945.0);
        expect(payment.isOpen, isTrue);
        expect(payment.paymentUrl, 'https://rzp.io/i/abc');
      },
    );

    test('listOrderPayments parses items', () async {
      final client = ApiClient(baseUrl: 'https://api.test');
      client.dio.httpClientAdapter = FakeHttpClientAdapter(
        (options) => jsonResponse({
          'items': [_payment(status: 'paid')],
        }, 200),
      );

      final result = await PaymentApi(client.dio).listOrderPayments('order-1');

      final items = result.when(onSuccess: (p) => p, onFailure: (_) => null);
      expect(items!.single.isPaid, isTrue);
      expect(items.single.paymentMethod, 'upi');
    });

    test('a 409 (nothing due) surfaces as a failure', () async {
      final client = ApiClient(baseUrl: 'https://api.test');
      client.dio.httpClientAdapter = FakeHttpClientAdapter(
        (options) => jsonResponse({
          'status': 409,
          'title': 'Conflict',
          'detail': 'Nothing is due on this order.',
        }, 409),
      );

      final result = await PaymentApi(client.dio).createPaymentLink('order-1');

      expect(
        result.when(onSuccess: (_) => false, onFailure: (_) => true),
        isTrue,
      );
    });
  });
}
