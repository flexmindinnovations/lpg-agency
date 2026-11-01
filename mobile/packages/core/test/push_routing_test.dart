import 'package:core/core.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('notificationRoute', () {
    test('returns null when there is no data', () {
      for (final app in PushApp.values) {
        expect(notificationRoute(app), isNull);
        expect(
          notificationRoute(app, referenceType: '', referenceId: ''),
          isNull,
        );
      }
    });

    test('customer', () {
      expect(
        notificationRoute(
          PushApp.customer,
          referenceType: 'order',
          referenceId: 'o1',
        ),
        '/orders/o1',
      );
      expect(
        notificationRoute(
          PushApp.customer,
          referenceType: 'invoice',
          referenceId: 'i1',
        ),
        '/orders/invoices/i1',
      );
      expect(
        notificationRoute(
          PushApp.customer,
          referenceType: 'complaint',
          referenceId: 'c1',
        ),
        '/support/c1',
      );
      expect(
        notificationRoute(
          PushApp.customer,
          referenceType: 'customer',
          referenceId: 'x',
        ),
        '/notifications',
      );
    });

    test('driver', () {
      expect(
        notificationRoute(
          PushApp.driver,
          referenceType: 'order',
          referenceId: 'o1',
        ),
        '/deliveries/stops/o1',
      );
      expect(
        notificationRoute(
          PushApp.driver,
          referenceType: 'route',
          referenceId: 'r1',
        ),
        '/',
      );
    });

    test('admin', () {
      expect(
        notificationRoute(
          PushApp.admin,
          referenceType: 'order',
          referenceId: 'o1',
        ),
        '/orders/o1',
      );
      expect(
        notificationRoute(
          PushApp.admin,
          referenceType: 'route',
          referenceId: 'r1',
        ),
        '/dispatch/trip/r1',
      );
      expect(
        notificationRoute(
          PushApp.admin,
          referenceType: 'complaint',
          referenceId: 'c1',
        ),
        '/complaints/c1',
      );
      expect(
        notificationRoute(
          PushApp.admin,
          referenceType: 'cash_handover',
          referenceId: 'h1',
        ),
        '/approvals',
      );
      expect(
        notificationRoute(
          PushApp.admin,
          referenceType: 'inventory_location',
          referenceId: 'l1',
        ),
        '/stock',
      );
      expect(
        notificationRoute(
          PushApp.admin,
          referenceType: 'unknown',
          referenceId: 'z',
        ),
        '/alerts',
      );
    });
  });

  group('DeepLinkGate', () {
    test('goes straight away when signed in', () {
      final gone = <String>[];
      final gate = DeepLinkGate(isAuthenticated: () => true, go: gone.add);
      gate.open('/orders/1');
      expect(gone, ['/orders/1']);
      expect(gate.pending, isNull);
    });

    test('holds the route until sign-in, then flushes once', () {
      var signedIn = false;
      final gone = <String>[];
      final gate = DeepLinkGate(isAuthenticated: () => signedIn, go: gone.add);
      gate.open('/orders/1');
      gate.flush();
      expect(gone, isEmpty);
      signedIn = true;
      gate.flush();
      gate.flush();
      expect(gone, ['/orders/1']);
    });
  });
}
