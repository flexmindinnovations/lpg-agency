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

    test('other notifications open the Alerts tab', () {
      expect(adminRouteFromData({'type': 'x'}), '/alerts');
    });

    test('a push with no data is not navigable', () {
      expect(adminRouteFromData({}), isNull);
    });
  });
}
