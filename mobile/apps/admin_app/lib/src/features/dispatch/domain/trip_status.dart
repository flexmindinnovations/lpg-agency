import 'package:design_system/design_system.dart';

/// Trip statuses a dispatcher still has to act on or watch.
const activeTripStatuses = ['planned', 'loaded', 'in_progress'];

/// Trips that are over, kept for the Past view.
const pastTripStatuses = ['completed', 'reconciled', 'cancelled'];

/// A trip's status in the office's words.
String tripStatusLabel(String status) => switch (status) {
  'planned' => 'Not loaded',
  'loaded' => 'Loaded',
  'in_progress' => 'On the road',
  'completed' => 'Completed',
  'reconciled' => 'Settled',
  'cancelled' => 'Cancelled',
  _ => LpgFormat.statusLabel(status),
};

LpgStatusSeverity tripStatusSeverity(String status) => switch (status) {
  'planned' => LpgStatusSeverity.neutral,
  'loaded' => LpgStatusSeverity.warning,
  'in_progress' => LpgStatusSeverity.info,
  'completed' || 'reconciled' => LpgStatusSeverity.success,
  _ => LpgStatusSeverity.danger,
};

/// Trips on the road first, then loaded, then not yet loaded.
int compareTrips(String a, String b) =>
    activeTripStatuses.indexOf(b).compareTo(activeTripStatuses.indexOf(a));
