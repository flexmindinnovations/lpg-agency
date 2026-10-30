import 'package:api_client/api_client.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/widgets.dart';

import '../../orders/data/orders_provider.dart';

/// Staff-facing names for the document types the backend keeps.
const complianceDocTypeLabels = <String, String>{
  'driving_licence': 'Driving licence',
  'dl_hazmat_endorsement': 'Hazmat endorsement on licence',
  'trem_card': 'TREM card',
  'driver_training_certificate': 'Driver training certificate',
  'vehicle_rc': 'Registration certificate (RC)',
  'vehicle_insurance': 'Vehicle insurance',
  'vehicle_fitness': 'Fitness certificate',
  'vehicle_puc': 'PUC certificate',
  'peso_transport_licence': 'PESO transport licence',
  'peso_form_f': 'PESO licence (Form F)',
  'insurance_policy': 'Agency insurance policy',
};

String complianceDocTypeLabel(String docType) =>
    complianceDocTypeLabels[docType] ?? LpgFormat.sentence(docType);

IconData complianceOwnerIcon(String ownerType) => switch (ownerType) {
  'driver' => LpgIcons.user,
  'vehicle' => LpgIcons.van,
  'warehouse' => LpgIcons.warehouse,
  _ => LpgIcons.agency,
};

/// Who or what a document belongs to, in words: the driver's name, the van's
/// registration, the godown's name.
String complianceOwnerName(ComplianceDocument doc, FleetData? fleet) {
  if (doc.ownerType == 'tenant') return 'Agency';
  if (fleet == null) {
    return switch (doc.ownerType) {
      'driver' => 'Driver',
      'vehicle' => 'Van',
      _ => 'Godown',
    };
  }
  return switch (doc.ownerType) {
    'driver' => fleet.driverName(doc.ownerId),
    'vehicle' => fleet.vehicleName(doc.ownerId),
    _ => fleet.warehouseName(doc.ownerId),
  };
}

/// How soon a document needs attention.
enum Urgency {
  expired('Expired'),
  thisMonth('Due within 30 days'),
  soon('Due within 90 days');

  const Urgency(this.heading);

  final String heading;

  LpgTone get tone => switch (this) {
    Urgency.expired => LpgTone.danger,
    Urgency.thisMonth => LpgTone.warning,
    Urgency.soon => LpgTone.info,
  };
}

Urgency urgencyFor(int daysLeft) {
  if (daysLeft < 0) return Urgency.expired;
  return daysLeft <= 30 ? Urgency.thisMonth : Urgency.soon;
}

/// "Expired 12 d ago", "Expires today", "Expires in 18 d".
String dueLabel(int daysLeft) {
  if (daysLeft < 0) return 'Expired ${-daysLeft} d ago';
  if (daysLeft == 0) return 'Expires today';
  return 'Expires in $daysLeft d';
}

/// The short form for a list row: "12 d ago", "Today", "18 d left".
String dueShort(int daysLeft) {
  if (daysLeft < 0) return '${-daysLeft} d ago';
  if (daysLeft == 0) return 'Today';
  return '$daysLeft d left';
}

/// Groups documents that carry an expiry into their [Urgency] bucket, soonest
/// first inside each. Documents with no expiry never lapse, so they drop out.
Map<Urgency, List<ComplianceDocument>> groupByUrgency(
  Iterable<ComplianceDocument> docs, [
  DateTime? today,
]) {
  final grouped = {for (final u in Urgency.values) u: <ComplianceDocument>[]};
  final dated = [
    for (final d in docs)
      if (d.daysLeft(today) != null) d,
  ]..sort((a, b) => a.daysLeft(today)!.compareTo(b.daysLeft(today)!));
  for (final d in dated) {
    grouped[urgencyFor(d.daysLeft(today)!)]!.add(d);
  }
  return grouped;
}

/// Documents of this type may legitimately carry no expiry date.
bool docTypeNeedsExpiry(String docType) => docType != 'trem_card';

/// What verification state reads like to staff.
String verificationLabel(String status) => switch (status) {
  'verified' => 'Verified',
  'rejected' => 'Rejected',
  _ => 'Not verified yet',
};

LpgStatusSeverity verificationSeverity(String status) => switch (status) {
  'verified' => LpgStatusSeverity.success,
  'rejected' => LpgStatusSeverity.danger,
  _ => LpgStatusSeverity.neutral,
};
