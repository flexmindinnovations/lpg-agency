import 'package:api_client/api_client.dart';
import 'package:flutter_test/flutter_test.dart';

import 'support/fake_http_client_adapter.dart';

void main() {
  test('getUpiQr passes the order id and decodes the QR image', () async {
    final client = ApiClient(baseUrl: 'https://api.test');
    String? query;
    client.dio.httpClientAdapter = FakeHttpClientAdapter((options) {
      query = options.uri.query;
      return jsonResponse({
        'upi_uri': 'upi://pay?pa=saigas@okhdfcbank&am=1250.00',
        'upi_id': 'saigas@okhdfcbank',
        'payee_name': 'Sai Gas Agency',
        'amount': '1250.00',
        'qr_png_base64': 'iVBORw0KGgo=',
      }, 200);
    });

    final result = await PaymentApi(client.dio).getUpiQr(orderId: 'ord-1');

    expect(query, 'order_id=ord-1');
    final qr = result.when(onSuccess: (q) => q, onFailure: (_) => null);
    expect(qr!.amount, 1250.0);
    expect(qr.payeeName, 'Sai Gas Agency');
    expect(qr.png, isNotEmpty);
  });

  test('getUpiQr maps a 409 (no UPI ID) to a failure', () async {
    final client = ApiClient(baseUrl: 'https://api.test');
    client.dio.httpClientAdapter = FakeHttpClientAdapter(
      (options) => jsonResponse({
        'error_code': 'CONFLICT',
        'detail': 'This agency has not set up a UPI ID yet.',
      }, 409),
    );

    final result = await PaymentApi(client.dio).getUpiQr(orderId: 'ord-1');

    final failure = result.when(onSuccess: (_) => null, onFailure: (f) => f);
    expect(failure!.errorCode, 'CONFLICT');
  });

  test('payment profile round-trips and reports what is set up', () {
    final profile = PaymentProfile.fromJson({
      'account_holder': 'Sai Gas Agency',
      'bank_name': 'HDFC Bank',
      'account_number': '50100123456789',
      'ifsc': 'HDFC0001234',
      'upi_id': 'saigas@okhdfcbank',
    });

    expect(profile.hasBankDetails, isTrue);
    expect(profile.hasUpi, isTrue);
    expect(profile.toJson()['ifsc'], 'HDFC0001234');
    expect(const PaymentProfile().hasUpi, isFalse);
  });

  test('cash book parses a day', () {
    final book = CashBook.fromJson({
      'date': '2026-10-28',
      'collections': [
        {'method': 'cash', 'payment_count': 3, 'amount': '2400.00'},
      ],
      'total_collected': '2400.00',
      'handover_count': 1,
      'expected_total': '2400.00',
      'handed_over_total': '2300.00',
      'shortfall_total': '100.00',
      'excess_total': '0.00',
      'accepted_total': '0.00',
      'disputed_total': '0.00',
      'pending_total': '2300.00',
      'pending_count': 1,
      'cash_in_hand_total': '500.00',
    });

    expect(book.collections.single.method, 'cash');
    expect(book.shortfallTotal, 100.0);
    expect(book.pendingCount, 1);
  });
}
