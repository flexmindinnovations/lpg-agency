import 'package:driver_app/src/features/delivery/data/location_sharing.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('LocationThrottle', () {
    test('accepts the first reading', () {
      final throttle = LocationThrottle();
      expect(throttle.accept(DateTime(2026, 9, 1, 12, 0, 0)), isTrue);
    });

    test('rejects a second reading inside the minimum interval', () {
      final throttle = LocationThrottle(minInterval: const Duration(seconds: 15));
      final t0 = DateTime(2026, 9, 1, 12, 0, 0);

      expect(throttle.accept(t0), isTrue);
      expect(throttle.accept(t0.add(const Duration(seconds: 5))), isFalse);
      expect(throttle.accept(t0.add(const Duration(seconds: 14))), isFalse);
    });

    test('accepts again once the interval has elapsed', () {
      final throttle = LocationThrottle(minInterval: const Duration(seconds: 15));
      final t0 = DateTime(2026, 9, 1, 12, 0, 0);

      expect(throttle.accept(t0), isTrue);
      expect(throttle.accept(t0.add(const Duration(seconds: 15))), isTrue);
      // ...and the window then restarts from that accepted reading.
      expect(throttle.accept(t0.add(const Duration(seconds: 20))), isFalse);
    });
  });
}
