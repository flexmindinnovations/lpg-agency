import 'package:api_client/api_client.dart';
import 'package:design_system/design_system.dart';

/// Customer-facing names for the complaint categories, in the order the
/// Raise a Complaint form offers them — safety first.
const complaintCategoryLabels = <String, String>{
  ComplaintCategory.gasLeakSafety: 'Gas leak / safety',
  ComplaintCategory.shortDelivery: 'Short Delivery',
  ComplaintCategory.damagedCylinder: 'Damaged Cylinder',
  ComplaintCategory.billingDispute: 'Billing Dispute',
  ComplaintCategory.driverConduct: 'Driver Conduct',
  ComplaintCategory.lateDelivery: 'Late Delivery',
  ComplaintCategory.other: 'Other',
};

/// Splits a PascalCase value from the backend (`"InProgress"`) into words
/// (`"In Progress"`).
String humanizePascalCase(String pascalCase) => pascalCase
    .replaceAllMapped(RegExp('(?<=[a-z])(?=[A-Z])'), (m) => ' ')
    .trim();

/// A complaint category as the customer reads it, never the raw enum.
String complaintCategoryLabel(String category) =>
    complaintCategoryLabels[category] ?? humanizePascalCase(category);

/// Badge colour for a complaint status, shared by the ticket list and the
/// ticket detail screen.
LpgStatusSeverity complaintStatusSeverity(String status) => switch (status) {
  'Resolved' || 'Closed' => LpgStatusSeverity.success,
  'InProgress' || 'Assigned' => LpgStatusSeverity.warning,
  'Open' => LpgStatusSeverity.info,
  'Rejected' => LpgStatusSeverity.danger,
  _ => LpgStatusSeverity.neutral,
};
