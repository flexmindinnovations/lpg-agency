import 'package:admin_app/src/push/push_notification_service.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('adminRouteFromData', () {
    test('an order notification opens the order page', () {
      expect(
        adminRouteFromData({'reference_type': 'order', 'reference_id': 'o-1'}),
        '/orders/o-1',
      );
    });

    test('each alert type opens the screen that handles it', () {
      String? route(String type, [String? id]) =>
          adminRouteFromData({'reference_type': type, 'reference_id': ?id});
      expect(route('complaint', 'c-1'), '/complaints/c-1');
      expect(route('route', 'r-1'), '/dispatch/trip/r-1');
      expect(route('customer', 'u-1'), '/customers/u-1');
      expect(route('cash_handover', 'h-1'), '/approvals');
      expect(route('inventory_location', 'w-1'), '/stock');
      expect(route('compliance_document', 'd-1'), '/compliance');
      expect(route('price_list_proposal', 'p-1'), '/pricing');
      expect(route('complaint'), '/alerts');
    });

    test('other notifications open the Alerts tab', () {
      expect(adminRouteFromData({'type': 'x'}), '/alerts');
    });

    test('a push with no data is not navigable', () {
      expect(adminRouteFromData({}), isNull);
    });
  });
}
