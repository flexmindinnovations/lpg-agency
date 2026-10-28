import 'package:design_system/design_system.dart';

/// The order's journey as the counter staff see it, one step per thing they
/// can act on. Mirrors the dashboard's order page.
const orderProgressSteps = [
  'Booked',
  'Confirmed',
  'On a trip',
  'Out for delivery',
  'Delivered',
];

const _progressStepByStatus = {
  'booked': 0,
  'confirmed': 1,
  'assigned': 2,
  'ready_for_dispatch': 2,
  'out_for_delivery': 3,
  'failed_delivery': 3,
  'delivered': 4,
  'closed': 4,
};

/// Index into [orderProgressSteps], or `null` when the order left the normal
/// path (cancelled).
int? orderProgressIndex(String status) => _progressStepByStatus[status];

/// Statuses a staff member can cancel straight away.
const _freeCancelStatuses = {
  'booked',
  'confirmed',
  'assigned',
  'ready_for_dispatch',
};

/// Statuses where a cancellation is a request a manager has to approve.
const _approvalCancelStatuses = {'out_for_delivery', 'failed_delivery'};

/// What the office can do with an order in [status]. [hasPendingCancellation]
/// is whether a post-dispatch cancellation request is waiting.
class OrderActions {
  const OrderActions(this.status, {this.hasPendingCancellation = false});

  final String status;
  final bool hasPendingCancellation;

  bool get canConfirm => status == 'booked';

  /// A confirmed order, or one on a trip whose van isn't loaded yet.
  bool get canSendOut => status == 'confirmed' || status == 'assigned';

  bool get canDepart => status == 'ready_for_dispatch';

  bool get canRecordDelivery => status == 'out_for_delivery';

  bool get canReschedule => status == 'failed_delivery';

  bool get canClose => status == 'delivered';

  /// Cancelling goes through at once.
  bool get canCancelNow => _freeCancelStatuses.contains(status);

  /// Cancelling asks a manager to approve; hidden once a request waits.
  bool get canRequestCancellation =>
      _approvalCancelStatuses.contains(status) && !hasPendingCancellation;

  /// A request is waiting for a manager to approve or reject.
  bool get canReviewCancellation =>
      _approvalCancelStatuses.contains(status) && hasPendingCancellation;
}

/// The chip's colour for an order status.
LpgStatusSeverity orderStatusSeverity(String status) => switch (status) {
  'delivered' || 'closed' => LpgStatusSeverity.success,
  'cancelled' || 'failed_delivery' => LpgStatusSeverity.danger,
  'out_for_delivery' => LpgStatusSeverity.info,
  'booked' => LpgStatusSeverity.neutral,
  _ => LpgStatusSeverity.warning,
};

/// The next-step hint shown above the actions, or `null` when there is
/// nothing to say. [tripLabel] describes the order's trip when known
/// (driver and van).
String? orderProgressNote(
  String status, {
  String? tripLabel,
}) => switch (status) {
  'booked' => 'Confirm the order to start preparing it.',
  'confirmed' => 'Next: send it out on a trip.',
  'assigned' =>
    tripLabel == null
        ? 'On a trip. The van still needs loading.'
        : 'On $tripLabel. The van still needs loading.',
  'ready_for_dispatch' =>
    tripLabel == null
        ? 'Loaded, waiting for the driver to leave.'
        : 'Loaded on $tripLabel, waiting for the driver to leave.',
  'out_for_delivery' =>
    'With the driver. Record the delivery with the customer\'s code once it is handed over.',
  'failed_delivery' =>
    'The delivery failed. Reschedule it to send it out again.',
  'delivered' => 'Delivered. Close the order once it is settled.',
  _ => null,
};

/// One order-list filter: a label and the statuses it covers.
class OrderFilter {
  const OrderFilter(this.label, this.statuses);

  final String label;

  /// Empty means every status.
  final Set<String> statuses;

  bool matches(String status) => statuses.isEmpty || statuses.contains(status);
}

const orderFilters = [
  OrderFilter('All', {}),
  OrderFilter('Booked', {'booked'}),
  OrderFilter('Confirmed', {'confirmed'}),
  OrderFilter('On a trip', {'assigned', 'ready_for_dispatch'}),
  OrderFilter('Out for delivery', {'out_for_delivery'}),
  OrderFilter('Failed', {'failed_delivery'}),
  OrderFilter('Delivered', {'delivered', 'closed'}),
  OrderFilter('Cancelled', {'cancelled'}),
];

/// Plain-words reasons for the failed-delivery form, keyed by backend code.
const failedDeliveryReasons = {
  'customer_unavailable': 'Customer unavailable',
  'wrong_address': 'Wrong address',
  'payment_refused': 'Payment refused',
  'vehicle_issue': 'Vehicle issue',
  'safety_issue': 'Safety issue',
};

/// What to do with the order next, keyed by backend code.
const failedDeliveryResolutions = {
  'reschedule': 'Reschedule',
  'cancel': 'Cancel the order',
  'return_stock': 'Return the stock',
};

/// Payment methods the office can record, keyed by backend code.
const paymentMethods = {
  'cash': 'Cash',
  'upi': 'UPI',
  'card': 'Card',
  'credit': 'On credit',
};

/// Failure messages in the order page's words; [code] is the API error code.
String? sendOutErrorMessage(String? code) => switch (code) {
  'INSUFFICIENT_STOCK' =>
    "The godown doesn't have enough filled cylinders for this order. Receive stock or pick another godown.",
  _ => null,
};

/// The first thing wrong with a load-out weighment entry, or `null`.
/// [underweight] is how many of the [cylinders] weighed short.
String? weighmentProblem({
  required String? scaleId,
  required int cylinders,
  required int underweight,
}) {
  if (scaleId == null) return 'Choose the scale you used.';
  if (cylinders < 1) return 'Enter how many cylinders you weighed.';
  if (underweight < 0) return 'The underweight count cannot be negative.';
  if (underweight > cylinders) {
    return 'More cylinders came up underweight than were weighed.';
  }
  return null;
}
