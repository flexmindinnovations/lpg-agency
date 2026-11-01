import 'package:customer_app/src/push/push_notification_service.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('customerRouteFromData', () {
    String? route(String type, [String? id]) =>
        customerRouteFromData({'reference_type': type, 'reference_id': ?id});

    test('opens the order, invoice or complaint the push is about', () {
      expect(route('order', 'o-1'), '/orders/o-1');
      expect(route('invoice', 'i-1'), '/orders/invoices/i-1');
      expect(route('complaint', 'c-1'), '/support/c-1');
    });

    test('a refill reminder opens the order form', () {
      expect(route('customer', 'u-1'), '/orders/new');
    });

    test(
      'anything else with data opens the inbox; no data is not navigable',
      () {
        expect(route('order'), '/notifications');
        expect(customerRouteFromData({'type': 'x'}), '/notifications');
        expect(customerRouteFromData({}), isNull);
      },
    );
  });
}
