import 'package:design_system/design_system.dart';

/// Badge colour for a complaint status, shared by the ticket list and the
/// ticket detail screen.
LpgStatusSeverity complaintStatusSeverity(String status) => switch (status) {
  'Resolved' || 'Closed' => LpgStatusSeverity.success,
  'InProgress' || 'Assigned' => LpgStatusSeverity.warning,
  'Open' => LpgStatusSeverity.info,
  'Rejected' => LpgStatusSeverity.danger,
  _ => LpgStatusSeverity.neutral,
};
