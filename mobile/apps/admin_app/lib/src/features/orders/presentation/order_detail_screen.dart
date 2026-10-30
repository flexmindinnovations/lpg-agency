import 'package:api_client/api_client.dart';
import 'package:core/core.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../api_result.dart';
import '../../../providers.dart';
import '../data/orders_provider.dart';
import '../domain/order_flow.dart';
import 'sheets/deliver_sheet.dart';
import 'sheets/order_action_sheets.dart';
import 'sheets/send_out_sheet.dart';

/// One order and everything the office can do with it, following the web
/// dashboard's order page: confirm, send out on a trip, record the delivery
/// (or its failure), reschedule, close, and cancel or review a cancellation.
class OrderDetailScreen extends ConsumerStatefulWidget {
  const OrderDetailScreen({super.key, required this.orderId});

  final String orderId;

  @override
  ConsumerState<OrderDetailScreen> createState() => _OrderDetailScreenState();
}

class _OrderDetailScreenState extends ConsumerState<OrderDetailScreen> {
  bool _busy = false;

  /// Reloads everything this order's screens show.
  void _reload() {
    ref.invalidate(adminOrderDetailProvider(widget.orderId));
    ref.invalidate(adminOrdersProvider);
    ref.invalidate(pendingCancellationProvider(widget.orderId));
    ref.invalidate(orderHistoryProvider(widget.orderId));
    ref.invalidate(activeTripsProvider);
  }

  /// Runs one API call, toasting [success] or the failure, then reloads.
  Future<void> _run<T>(
    Future<Result<T>> Function() call,
    String success,
  ) async {
    setState(() => _busy = true);
    final result = await call();
    if (!mounted) return;
    setState(() => _busy = false);
    switch (result) {
      case Success<T>():
        LpgFeedback.showToast(context, success, tone: LpgTone.success);
        _reload();
      case FailureResult<T>(:final failure):
        LpgFeedback.showToast(context, failure.message, tone: LpgTone.danger);
    }
  }

  /// Shows a form sheet; on `true` toasts [success] and reloads.
  Future<void> _sheet(
    String title,
    Widget Function() builder,
    String success,
  ) async {
    final done = await LpgFeedback.showSheet<bool>(
      context,
      title: title,
      builder: (_) => builder(),
    );
    if (done != true || !mounted) return;
    LpgFeedback.showToast(context, success, tone: LpgTone.success);
    _reload();
  }

  Future<void> _confirm(OrderResponse order) => _run(
    () => ref.read(orderApiProvider).confirmOrder(order.id),
    'Order confirmed.',
  );

  Future<void> _depart(OrderResponse order) => _run(
    () => ref.read(orderApiProvider).departOrder(order.id),
    'Marked out for delivery. The customer was sent a delivery code.',
  );

  Future<void> _close(OrderResponse order) => _run(
    () => ref.read(orderApiProvider).closeOrder(order.id),
    'Order closed.',
  );

  Future<void> _approveCancellation(OrderResponse order) async {
    final ok = await LpgFeedback.confirm(
      context,
      title: 'Approve cancellation?',
      message: 'The order will be cancelled and the stock returned.',
      confirmLabel: 'Approve',
      destructive: true,
    );
    if (!ok || !mounted) return;
    await _run(
      () => ref.read(orderApiProvider).approveCancellation(order.id),
      'Cancellation approved.',
    );
  }

  void _rejectCancellation(OrderResponse order) => _sheet(
    'Reject cancellation',
    () => ReasonSheet(
      intro: 'The order carries on. The person who asked sees your reason.',
      label: 'Reason',
      actionLabel: 'Reject request',
      submit: (reason) =>
          ref.read(orderApiProvider).rejectCancellation(order.id, reason),
    ),
    'Cancellation request rejected. The order carries on.',
  );

  /// Cancelling is immediate before dispatch; after it, a manager approves.
  void _cancel(OrderResponse order, OrderActions actions) {
    final immediate = actions.canCancelNow;
    _sheet(
      immediate ? 'Cancel order' : 'Request cancellation',
      () => ReasonSheet(
        intro: immediate
            ? 'The order is cancelled straight away.'
            : 'The order is already out. A manager has to approve the cancellation.',
        label: 'Reason',
        actionLabel: immediate ? 'Cancel order' : 'Send request',
        destructive: true,
        submit: (reason) =>
            ref.read(orderApiProvider).cancelOrder(order.id, reason),
      ),
      immediate ? 'Order cancelled.' : 'Cancellation requested.',
    );
  }

  @override
  Widget build(BuildContext context) {
    final orderAsync = ref.watch(adminOrderDetailProvider(widget.orderId));

    return Scaffold(
      appBar: AppBar(
        title: Text(
          orderAsync.maybeWhen(
            data: (o) => LpgFormat.orderNumber(o.orderNumber, o.id),
            orElse: () => 'Order details',
          ),
        ),
        actions: [
          IconButton(
            tooltip: 'Refresh',
            icon: const Icon(LpgIcons.sync),
            onPressed: _reload,
          ),
        ],
      ),
      body: orderAsync.when(
        loading: () => const Center(child: LpgLoadingIndicator()),
        error: (err, _) => LpgErrorState(
          message: errorMessage(err),
          onRetry: () =>
              ref.invalidate(adminOrderDetailProvider(widget.orderId)),
        ),
        data: _buildOrder,
      ),
    );
  }

  Widget _buildOrder(OrderResponse order) {
    final colors = context.lpgColors;
    final text = context.lpgText;
    final names = ref.watch(cylinderNamesProvider).value ?? const {};

    final onTripStatus = const {
      'assigned',
      'ready_for_dispatch',
      'out_for_delivery',
    }.contains(order.status);
    final awaitingCancel = const {
      'out_for_delivery',
      'failed_delivery',
    }.contains(order.status);

    final trips = onTripStatus
        ? ref.watch(activeTripsProvider(order.branchId)).value
        : null;
    RouteSummary? trip;
    for (final t in trips ?? const <RouteSummary>[]) {
      if (t.stops.any((s) => s.id == order.routeStopId)) trip = t;
    }
    String? tripLabel;
    if (trip != null) {
      final fleet = ref.watch(fleetProvider).value;
      if (fleet != null) {
        tripLabel =
            '${fleet.vehicleName(trip.vehicleId)} with '
            '${fleet.driverName(trip.driverId)}';
      }
    }

    final pending = awaitingCancel
        ? ref.watch(pendingCancellationProvider(order.id)).value
        : null;
    final actions = OrderActions(
      order.status,
      hasPendingCancellation: pending != null,
    );

    String? failedReason;
    if (order.status == 'failed_delivery') {
      final history = ref.watch(orderHistoryProvider(order.id)).value;
      for (final entry in history ?? const <OrderStatusHistoryEntry>[]) {
        if (entry.toStatus == 'failed_delivery' && entry.reason != null) {
          failedReason = failedDeliveryReasons[entry.reason] ?? entry.reason;
        }
      }
    }

    // A booked order has no price until the agency confirms it.
    final priced = order.status != 'booked' || (order.totalAmount ?? 0) > 0;
    final note = orderProgressNote(order.status, tripLabel: tripLabel);
    final progress = orderProgressIndex(order.status);

    return RefreshIndicator(
      onRefresh: () async => _reload(),
      child: SingleChildScrollView(
        padding: LpgSpacing.page,
        physics: const AlwaysScrollableScrollPhysics(),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            LpgCard(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Flexible(
                        child: Text(
                          LpgFormat.orderNumber(order.orderNumber, order.id),
                          style: text.headlineSmall,
                        ),
                      ),
                      LpgStatusBadge(
                        label: LpgFormat.statusLabel(order.status),
                        severity: orderStatusSeverity(order.status),
                      ),
                    ],
                  ),
                  const SizedBox(height: LpgSpacing.sm),
                  Text(order.customerName ?? 'Customer', style: text.bodyLarge),
                  const SizedBox(height: LpgSpacing.xs),
                  Text(
                    order.deliveryAddress.addressLine,
                    style: text.bodyMedium?.copyWith(
                      color: colors.textSecondary,
                    ),
                  ),
                  const SizedBox(height: LpgSpacing.xs),
                  Text(
                    'Requested for ${LpgFormat.date(order.requestedDate)}',
                    style: text.bodyMedium?.copyWith(
                      color: colors.textSecondary,
                    ),
                  ),
                ],
              ),
            ),
            if (order.status == 'cancelled') ...[
              const SizedBox(height: LpgSpacing.md),
              const LpgBanner(
                tone: LpgTone.danger,
                message: 'This order was cancelled.',
              ),
            ] else if (progress != null) ...[
              const SizedBox(height: LpgSpacing.lg),
              LpgTimeline(steps: _timelineSteps(order.status, progress)),
            ],
            if (note != null) ...[
              const SizedBox(height: LpgSpacing.md),
              LpgBanner(message: note),
            ],
            if (failedReason != null) ...[
              const SizedBox(height: LpgSpacing.sm),
              LpgBanner(
                tone: LpgTone.warning,
                title: 'Why it failed',
                message: failedReason,
              ),
            ],
            if (pending != null) ...[
              const SizedBox(height: LpgSpacing.sm),
              LpgBanner(
                tone: LpgTone.warning,
                title: 'Cancellation requested',
                message: pending.reason,
              ),
            ],
            const SizedBox(height: LpgSpacing.lg),
            Text('Order lines', style: text.titleMedium),
            const SizedBox(height: LpgSpacing.sm),
            for (final line in order.lines)
              Padding(
                padding: const EdgeInsets.only(bottom: LpgSpacing.xs),
                child: LpgCard(
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              names[line.cylinderTypeId] ?? 'Cylinder',
                              style: text.bodyLarge,
                            ),
                            Text(
                              'Quantity: ${line.quantityOrdered}',
                              style: text.bodySmall?.copyWith(
                                color: colors.textSecondary,
                              ),
                            ),
                          ],
                        ),
                      ),
                      Text(
                        priced
                            ? LpgFormat.currency(
                                (line.unitPrice ?? 0.0) * line.quantityOrdered,
                              )
                            : 'Priced on confirmation',
                        style: priced
                            ? text.titleSmall
                            : text.bodySmall?.copyWith(
                                color: colors.textSecondary,
                              ),
                      ),
                    ],
                  ),
                ),
              ),
            const SizedBox(height: LpgSpacing.sm),
            LpgCard(
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text('Total amount', style: text.titleMedium),
                  Text(
                    priced
                        ? LpgFormat.currency(order.totalAmount ?? 0.0)
                        : 'On confirmation',
                    style: priced
                        ? text.headlineSmall?.copyWith(
                            color: colors.actionPrimary,
                          )
                        : text.bodyMedium?.copyWith(
                            color: colors.textSecondary,
                          ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: LpgSpacing.xl),
            ..._buildActions(order, actions, trip),
            const SizedBox(height: LpgSpacing.xl),
          ],
        ),
      ),
    );
  }

  List<LpgTimelineStep> _timelineSteps(String status, int progress) {
    final finished = status == 'delivered' || status == 'closed';
    return [
      for (var i = 0; i < orderProgressSteps.length; i++)
        LpgTimelineStep(
          title: orderProgressSteps[i],
          state: finished || i < progress
              ? LpgTimelineState.done
              : i == progress
              ? (status == 'failed_delivery'
                    ? LpgTimelineState.failed
                    : LpgTimelineState.current)
              : LpgTimelineState.upcoming,
        ),
    ];
  }

  List<Widget> _buildActions(
    OrderResponse order,
    OrderActions actions,
    RouteSummary? trip,
  ) {
    Widget button(
      String label,
      VoidCallback onPressed, {
      LpgButtonVariant variant = LpgButtonVariant.primary,
      IconData? icon,
    }) => Padding(
      padding: const EdgeInsets.only(bottom: LpgSpacing.sm),
      child: LpgButton(
        label: label,
        variant: variant,
        icon: icon,
        expand: true,
        isLoading: _busy,
        onPressed: _busy ? null : onPressed,
      ),
    );

    return [
      if (actions.canConfirm)
        button('Confirm order', () => _confirm(order), icon: LpgIcons.check),
      if (actions.canSendOut)
        button(
          'Send out',
          () => _sheet(
            'Send out',
            () => SendOutSheet(order: order, currentTrip: trip),
            'Loaded and handed to the driver.',
          ),
          icon: LpgIcons.truck,
        ),
      if (actions.canDepart)
        button(
          'Mark as out for delivery',
          () => _depart(order),
          icon: LpgIcons.truck,
        ),
      if (actions.canRecordDelivery) ...[
        button(
          'Record delivery',
          () => _sheet(
            'Record delivery',
            () => DeliverSheet(order: order),
            'Delivery recorded.',
          ),
          icon: LpgIcons.check,
        ),
        button(
          'Delivery failed',
          () => _sheet(
            'Delivery failed',
            () => FailedDeliverySheet(order: order),
            'Failed delivery recorded.',
          ),
          variant: LpgButtonVariant.secondary,
        ),
      ],
      if (actions.canReschedule)
        button(
          'Reschedule',
          () => _sheet(
            'Reschedule delivery',
            () => RescheduleSheet(order: order),
            'Delivery rescheduled. Send it out again when ready.',
          ),
          icon: LpgIcons.calendar,
        ),
      if (actions.canClose)
        button('Close order', () => _close(order), icon: LpgIcons.check),
      if (actions.canReviewCancellation) ...[
        button(
          'Approve cancellation',
          () => _approveCancellation(order),
          variant: LpgButtonVariant.destructive,
        ),
        button(
          'Reject request',
          () => _rejectCancellation(order),
          variant: LpgButtonVariant.secondary,
        ),
      ],
      if (actions.canCancelNow || actions.canRequestCancellation)
        button(
          actions.canCancelNow ? 'Cancel order' : 'Request cancellation',
          () => _cancel(order, actions),
          variant: LpgButtonVariant.text,
        ),
    ];
  }
}
