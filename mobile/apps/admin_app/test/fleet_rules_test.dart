import 'package:admin_app/src/features/fleet/domain/fleet_rules.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('expiryState', () {
    final today = DateTime(2026, 10, 28);

    test('flags lapsed, soon and valid documents', () {
      expect(
        expiryState(DateTime(2026, 10, 27), today: today),
        ExpiryState.expired,
      );
      expect(
        expiryState(DateTime(2026, 10, 28), today: today),
        ExpiryState.expiring,
      );
      expect(
        expiryState(DateTime(2026, 11, 27), today: today),
        ExpiryState.expiring,
      );
      expect(
        expiryState(DateTime(2026, 11, 28), today: today),
        ExpiryState.valid,
      );
      expect(expiryState(null, today: today), ExpiryState.unknown);
    });
  });

  group('status moves', () {
    test('inactive is final for drivers and vans', () {
      expect(driverStatusTargets['inactive'], isEmpty);
      expect(vehicleStatusTargets['inactive'], isEmpty);
    });

    test('active can pause or retire', () {
      expect(driverStatusTargets['active'], ['on_leave', 'inactive']);
      expect(vehicleStatusTargets['active'], ['maintenance', 'inactive']);
    });
  });

  group('normalizeMobile', () {
    test('accepts the usual ways of typing a number', () {
      expect(normalizeMobile('98765 43210'), '+919876543210');
      expect(normalizeMobile('09876543210'), '+919876543210');
      expect(normalizeMobile('+91 98765 43210'), '+919876543210');
    });

    test('rejects short and long numbers', () {
      expect(normalizeMobile('12345'), isNull);
      expect(normalizeMobile('987654321012345'), isNull);
    });
  });

  test('normalizeRegistration strips spaces and dashes', () {
    expect(normalizeRegistration('mh 12-ab 1234'), 'MH12AB1234');
  });
}
