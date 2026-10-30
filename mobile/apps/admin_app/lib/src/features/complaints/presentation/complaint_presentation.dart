import 'package:api_client/api_client.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/widgets.dart';

/// Staff-facing names for the complaint categories.
const complaintCategoryLabels = <String, String>{
  'GasLeakSafety': 'Gas leak / safety',
  'ShortDelivery': 'Short delivery',
  'DamagedCylinder': 'Damaged cylinder',
  'BillingDispute': 'Billing dispute',
  'DriverConduct': 'Driver conduct',
  'LateDelivery': 'Late delivery',
  'Other': 'Other',
};

/// `InProgress` -> `In progress`.
String humanizeStatus(String pascalCase) => pascalCase
    .replaceAllMapped(RegExp('(?<=[a-z])(?=[A-Z])'), (m) => ' ')
    .toLowerCase()
    .replaceFirstMapped(RegExp('^.'), (m) => m[0]!.toUpperCase());

String complaintCategoryLabel(String category) =>
    complaintCategoryLabels[category] ?? humanizeStatus(category);

IconData complaintCategoryIcon(String category) => switch (category) {
  'GasLeakSafety' => LpgIcons.warning,
  'ShortDelivery' => LpgIcons.package,
  'DamagedCylinder' => LpgIcons.cylinder,
  'BillingDispute' => LpgIcons.invoice,
  'DriverConduct' => LpgIcons.user,
  'LateDelivery' => LpgIcons.clock,
  _ => LpgIcons.complaint,
};

LpgStatusSeverity complaintStatusSeverity(String status) => switch (status) {
  'Resolved' || 'Closed' => LpgStatusSeverity.success,
  'InProgress' || 'Assigned' => LpgStatusSeverity.warning,
  'Open' => LpgStatusSeverity.info,
  'Rejected' => LpgStatusSeverity.danger,
  _ => LpgStatusSeverity.neutral,
};

LpgStatusSeverity complaintPrioritySeverity(String priority) =>
    switch (priority) {
      'Critical' => LpgStatusSeverity.danger,
      'High' => LpgStatusSeverity.warning,
      'Medium' => LpgStatusSeverity.info,
      _ => LpgStatusSeverity.neutral,
    };

/// How long a span reads: "40 min", "5 h", "3 d".
String _span(Duration d) {
  final minutes = d.inMinutes.abs();
  if (minutes < 60) return '${minutes < 1 ? 1 : minutes} min';
  if (minutes < 48 * 60) return '${(minutes / 60).round()} h';
  return '${(minutes / (24 * 60)).round()} d';
}

/// "Overdue by 3 h" or "Due in 5 h"; `null` when the complaint is finished or
/// has no deadline.
String? slaLabel(ComplaintResponse complaint, [DateTime? now]) {
  final due = complaint.slaDueAt;
  if (complaint.isFinished || due == null) return null;
  final left = due.difference(now ?? DateTime.now());
  return left.isNegative
      ? 'Overdue by ${_span(left)}'
      : 'Due in ${_span(left)}';
}

/// How long ago a time was: "12 min ago", "5 h ago", "3 d ago".
String ago(DateTime time, [DateTime? now]) =>
    '${_span((now ?? DateTime.now()).difference(time))} ago';

/// What the person resolving a complaint can conclude.
const resolutionOutcomes = <String, String>{
  'Resolved': 'Resolved',
  'Compensated': 'Compensated',
  'Rejected': 'Rejected',
};
