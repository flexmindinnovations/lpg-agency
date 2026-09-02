import 'package:driver_app/src/push/push_notification_service.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('driverRouteFromData', () {
    test('an order push opens that stop', () {
      expect(
        driverRouteFromData({
          'type': 'driver_assigned',
          'reference_type': 'order',
          'reference_id': 'abc123',
        }),
        '/stops/abc123',
      );
    });

    test('a route push opens the Today tab', () {
      expect(
        driverRouteFromData({'type': 'route_ready', 'reference_type': 'route'}),
        '/',
      );
    });

    test('an order push without an id falls back to Today', () {
      expect(driverRouteFromData({'reference_type': 'order'}), '/');
    });

    test('any other push with data falls back to Today', () {
      expect(driverRouteFromData({'type': 'something_new'}), '/');
    });

    test('a push with no data is not navigable', () {
      expect(driverRouteFromData(const {}), isNull);
    });
  });
}
