import 'package:api_client/api_client.dart';
import 'package:design_system/design_system.dart';

/// Days before expiry at which a licence or RC is flagged.
const documentWarningDays = 30;

/// Where a licence or RC stands against today.
enum ExpiryState { expired, expiring, valid, unknown }

ExpiryState expiryState(DateTime? expiry, {DateTime? today}) {
  if (expiry == null) return ExpiryState.unknown;
  final now = today ?? DateTime.now();
  final days = DateTime.utc(
    expiry.year,
    expiry.month,
    expiry.day,
  ).difference(DateTime.utc(now.year, now.month, now.day)).inDays;
  if (days < 0) return ExpiryState.expired;
  return days <= documentWarningDays ? ExpiryState.expiring : ExpiryState.valid;
}

/// What a dispatcher may move a driver to; "inactive" is final, as on the
/// dashboard.
const driverStatusTargets = {
  'active': ['on_leave', 'inactive'],
  'on_leave': ['active', 'inactive'],
  'inactive': <String>[],
};

/// What a dispatcher may move a van to; "inactive" is final.
const vehicleStatusTargets = {
  'active': ['maintenance', 'inactive'],
  'maintenance': ['active', 'inactive'],
  'inactive': <String>[],
};

String fleetStatusLabel(String status) => switch (status) {
  'active' => 'Active',
  'on_leave' => 'On leave',
  'maintenance' => 'In maintenance',
  'inactive' => 'Inactive',
  _ => LpgFormat.statusLabel(status),
};

LpgStatusSeverity fleetStatusSeverity(String status) => switch (status) {
  'active' => LpgStatusSeverity.success,
  'on_leave' || 'maintenance' => LpgStatusSeverity.warning,
  _ => LpgStatusSeverity.neutral,
};

/// The action label that moves a driver or van to [status].
String fleetStatusAction(String status) => switch (status) {
  'active' => 'Mark active',
  'on_leave' => 'Mark on leave',
  'maintenance' => 'Send for maintenance',
  'inactive' => 'Deactivate',
  _ => fleetStatusLabel(status),
};

const ownershipTypes = {
  'owned': 'Owned',
  'third_party': 'Third party',
  'rental': 'Rental',
  'gig': 'Gig',
};

/// Capital letters and digits only, the way a registration plate is read.
String normalizeRegistration(String value) =>
    value.toUpperCase().replaceAll(RegExp(r'[\s-]'), '');

/// A 10-digit Indian mobile number from whatever was typed, or null.
String? normalizeMobile(String value) {
  var digits = value.replaceAll(RegExp(r'\D'), '');
  if (digits.length == 12 && digits.startsWith('91')) {
    digits = digits.substring(2);
  } else if (digits.length == 11 && digits.startsWith('0')) {
    digits = digits.substring(1);
  }
  return digits.length == 10 ? '+91$digits' : null;
}

/// Branch name for [id], falling back to a neutral word (never a UUID).
String branchName(List<FleetBranch> branches, String id) {
  for (final b in branches) {
    if (b.id == id) return b.name;
  }
  return 'Branch';
}
