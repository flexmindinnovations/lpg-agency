import 'package:api_client/api_client.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/widgets.dart';

/// How an order's status is shown everywhere in the Customer App — the
/// order list, order detail, tracking and the dashboard all read from here,
/// so a status can never be green on one screen and amber on the next.
extension OrderPresentation on OrderResponse {
  /// `Order ORD000027`: the number customers quote to support, the same
  /// one the agency sees on the dashboard.
  String get reference => 'Order ${LpgFormat.orderNumber(orderNumber, id)}';

  String get statusLabel => LpgFormat.statusLabel(status);

  LpgStatusSeverity get statusSeverity => orderStatusSeverity(status);

  IconData get statusIcon => switch (status) {
    'delivered' || 'closed' => LpgIcons.success,
    'cancelled' || 'failed_delivery' => LpgIcons.cancel,
    'out_for_delivery' => LpgIcons.truck,
    'ready_for_dispatch' => LpgIcons.package,
    _ => LpgIcons.orders,
  };

  /// Whether the driver is on the way, so the order can be tracked live.
  bool get isTrackable => status == 'out_for_delivery';

  /// The amount as a list shows it: the confirmed total, "Not charged" for
  /// an order cancelled before it was priced, otherwise "To be confirmed"
  /// (the agency prices an order when confirming it).
  String get amountLabel {
    if (amountToPay case final total?) return LpgFormat.currency(total);
    return status == 'cancelled' ? 'Not charged' : 'To be confirmed';
  }

  int get cylinderCount =>
      lines.fold<int>(0, (sum, line) => sum + line.quantityOrdered);
}

LpgStatusSeverity orderStatusSeverity(String status) => switch (status) {
  'delivered' || 'closed' => LpgStatusSeverity.success,
  'cancelled' || 'failed_delivery' => LpgStatusSeverity.danger,
  'out_for_delivery' || 'ready_for_dispatch' => LpgStatusSeverity.warning,
  _ => LpgStatusSeverity.info,
};

/// How a payment method reads to a customer.
String paymentMethodLabel(String method) => switch (method) {
  'cash' => 'Cash on delivery',
  'upi' => 'UPI',
  'card' => 'Card',
  'online_gateway' => 'Online payment',
  'credit' => 'Credit account',
  _ => LpgFormat.sentence(method),
};
