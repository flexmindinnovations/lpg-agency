import 'package:api_client/api_client.dart';
import 'package:design_system/design_system.dart';

/// How an invoice is labelled on the list and detail screens.
extension InvoicePresentation on InvoiceResponse {
  /// `invoiceNumber` already carries the backend's own "INV-..." prefix —
  /// only the UUID fallback needs one added, or this doubles up into
  /// "INV-INV-2026-000011".
  String get reference =>
      invoiceNumber ?? 'INV-${invoiceId.substring(0, 8).toUpperCase()}';

  String get statusLabel => LpgFormat.statusLabel(status);

  LpgStatusSeverity get statusSeverity => switch (status) {
    'paid' => LpgStatusSeverity.success,
    'partially_paid' => LpgStatusSeverity.warning,
    'issued' => LpgStatusSeverity.info,
    'cancelled' || 'refunded' => LpgStatusSeverity.danger,
    _ => LpgStatusSeverity.neutral,
  };

  double get balanceDue => totalAmount - amountPaid;
}
