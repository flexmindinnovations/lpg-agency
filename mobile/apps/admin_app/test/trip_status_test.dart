import 'package:admin_app/src/features/dispatch/domain/trip_status.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('trip statuses read in the office\'s words', () {
    expect(tripStatusLabel('planned'), 'Not loaded');
    expect(tripStatusLabel('in_progress'), 'On the road');
  });

  test('trips on the road sort before loaded and not-loaded ones', () {
    final statuses = ['planned', 'in_progress', 'loaded']..sort(compareTrips);
    expect(statuses, ['in_progress', 'loaded', 'planned']);
  });
}
