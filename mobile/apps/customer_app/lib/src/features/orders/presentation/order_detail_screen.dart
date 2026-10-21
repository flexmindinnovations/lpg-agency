import 'package:api_client/api_client.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../providers.dart';
import '../../payments/presentation/pay_online_section.dart';
import '../data/cylinder_types_provider.dart';
import '../data/invoices_provider.dart';
import '../data/orders_provider.dart';
import 'order_placement_screen.dart' show ReorderDraft;
import 'order_presentation.dart';
import 'widgets/delivery_code_card.dart';

/// Statuses a customer can still cancel from, mirroring the backend's
/// order state machine (D-19): free before dispatch, a Manager-approved
/// request once the driver is on the way (`pendingApproval: true`). Listed
/// positively so a status the app doesn't know about (`closed`, or one
/// added later) never offers Cancel.
const _cancellableStatuses = {
  'booked',
  'confirmed',
  'assigned',
  'ready_for_dispatch',
  'out_for_delivery',
};

/// Statuses in which the backend accepts an online prepayment: the price is
/// fixed (`confirmed`) and the cylinders have not been delivered yet. After
/// delivery, the balance is paid from the invoice instead. Not offered on a
/// failed delivery: the agency first has to arrange another attempt.
const _prepayableStatuses = {
  'confirmed',
  'assigned',
  'ready_for_dispatch',
  'out_for_delivery',
};

class OrderDetailScreen extends ConsumerWidget {
  const OrderDetailScreen({super.key, required this.orderId});

  final String orderId;

  void _refreshAll(WidgetRef ref) {
    ref.invalidate(orderDetailProvider(orderId));
    ref.invalidate(pendingCancellationProvider(orderId));
    ref.invalidate(deliveryCodeProvider(orderId));
    ref.invalidate(orderHistoryProvider(orderId));
    ref.invalidate(ordersProvider);
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    // Live status updates over /ws (RealtimeClient.subscribeToOrder) --
    // confirmed/assigned/out-for-delivery/delivered land here without a
    // manual refresh. The event carries only the order id and status
    // (realtime_handlers.py's on_order_status_changed), so refetch via
    // orderDetailProvider rather than trying to patch state from the message.
    ref.listen(orderRealtimeProvider(orderId), (previous, next) {
      next.whenData((event) {
        _refreshAll(ref);
        final status = event['status'];
        LpgFeedback.showToast(
          context,
          status is String
              ? 'Your order is now ${LpgFormat.sentence(status).toLowerCase()}.'
              : 'Your order was updated.',
          tone: LpgTone.info,
        );
      });
    });

    final orderAsync = ref.watch(orderDetailProvider(orderId));

    return Scaffold(
      appBar: AppBar(title: const Text('Order Details')),
      body: orderAsync.when(
        loading: () => const LpgSkeletonList(itemCount: 4),
        error: (err, _) => LpgErrorState(
          message: 'Failed to load this order\n$err',
          onRetry: () => ref.refresh(orderDetailProvider(orderId)),
        ),
        data: (order) {
          final pendingCancel = ref
              .watch(pendingCancellationProvider(orderId))
              .asData
              ?.value;
          final cancellable =
              _cancellableStatuses.contains(order.status) &&
              pendingCancel == null;
          final sections = <Widget>[
            _SummaryCard(order: order),
            if (pendingCancel != null) ...[
              const SizedBox(height: LpgSpacing.md),
              LpgBanner(
                key: const Key('cancellation-pending'),
                tone: LpgTone.warning,
                icon: LpgIcons.pending,
                title: 'Cancellation requested',
                message:
                    'Sent ${LpgFormat.dateTime(pendingCancel.requestedAt)}. '
                    'The driver had already set out, so the agency has to '
                    'approve it. Reason: ${pendingCancel.reason}',
              ),
            ],
            if (order.status == 'failed_delivery') ...[
              const SizedBox(height: LpgSpacing.md),
              _FailedDeliveryBanner(orderId: orderId),
            ],
            if (order.isTrackable && pendingCancel == null) ...[
              const SizedBox(height: LpgSpacing.md),
              DeliveryCodeCard(orderId: orderId),
            ],
            const LpgSectionHeader(title: 'Delivery address'),
            LpgCard(
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const LpgIconBox(icon: LpgIcons.location),
                  const SizedBox(width: LpgSpacing.smd),
                  Expanded(
                    child: Text(
                      order.deliveryAddress.addressLine,
                      style: context.lpgText.bodyLarge,
                    ),
                  ),
                ],
              ),
            ),
            const LpgSectionHeader(title: 'Cylinders'),
            _LinesCard(order: order),
            const SizedBox(height: LpgSpacing.md),
            _TotalCard(order: order),
            const SizedBox(height: LpgSpacing.lg),
            if (pendingCancel == null)
              PayOnlineSection(
                orderId: orderId,
                canPay: _prepayableStatuses.contains(order.status),
                onPaid: () => ref.invalidate(orderDetailProvider(orderId)),
              ),
            if (order.isTrackable)
              LpgButton(
                label: 'Track Delivery',
                icon: LpgIcons.navigate,
                expand: true,
                onPressed: () => context.push('/orders/$orderId/track'),
              ),
            if (order.status == 'delivered' || order.status == 'closed')
              _DeliveredActions(order: order),
            if (cancellable) ...[
              if (order.isTrackable) const SizedBox(height: LpgSpacing.smd),
              LpgButton(
                label: 'Cancel Order',
                icon: LpgIcons.cancel,
                variant: LpgButtonVariant.secondary,
                expand: true,
                onPressed: () => _confirmCancel(context, ref),
              ),
            ],
          ];

          return RefreshIndicator(
            onRefresh: () {
              _refreshAll(ref);
              return ref.refresh(orderDetailProvider(orderId).future);
            },
            child: ListView(
              physics: const AlwaysScrollableScrollPhysics(),
              padding: LpgSpacing.page,
              children: [
                for (var i = 0; i < sections.length; i++)
                  LpgFadeSlideIn(index: i, child: sections[i]),
              ],
            ),
          );
        },
      ),
    );
  }

  Future<void> _confirmCancel(BuildContext context, WidgetRef ref) async {
    final reason = await showDialog<String>(
      context: context,
      builder: (dialogContext) => const _CancelDialog(),
    );

    if (reason == null || reason.isEmpty || !context.mounted) return;

    final result = await ref
        .read(orderApiProvider)
        .cancelOrder(orderId, reason);

    if (!context.mounted) return;

    result.when(
      onSuccess: (response) {
        // Pop back to the orders list *before* touching either provider,
        // then invalidate — not the reverse. Invalidating
        // `orderDetailProvider(orderId)` while still on this screen (it's
        // exactly what `build()` watches, and cancelling flips
        // `cancellable` to false, which removes this very Cancel button
        // from the tree mid-rebuild) reproduced a framework
        // `_dependents.isEmpty` assertion live, consistently, across
        // several variations of "stay and refresh in place." Popping
        // first sidesteps the whole class of problem rather than chasing
        // its exact mechanism further; `ordersProvider`'s own list
        // already reflects the new status once it reloads.
        final messenger = ScaffoldMessenger.of(context);
        Navigator.of(context).pop();
        ref.invalidate(ordersProvider);
        ref.invalidate(pendingCancellationProvider(orderId));
        messenger.showSnackBar(
          SnackBar(
            content: Text(
              response.pendingApproval
                  ? 'Cancellation requested. The driver had already set '
                        'out, so the agency needs to approve it.'
                  : 'Order cancelled.',
            ),
          ),
        );
      },
      onFailure: (failure) => LpgFeedback.showToast(
        context,
        'Could not cancel the order: ${failure.message}',
        tone: LpgTone.danger,
      ),
    );
  }
}

/// Asks for a reason before cancelling. An empty reason shows an inline
/// message instead of silently ignoring the tap (CA-11).
class _CancelDialog extends StatefulWidget {
  const _CancelDialog();

  @override
  State<_CancelDialog> createState() => _CancelDialogState();
}

class _CancelDialogState extends State<_CancelDialog> {
  final _controller = TextEditingController();
  String? _error;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _close([String? reason]) {
    // Unfocus before popping: dismissing a route while its own TextField
    // is still IME-focused is a known trigger for a framework-level
    // `_dependents.isEmpty` assertion crash — confirmed live on this
    // exact dialog.
    FocusScope.of(context).unfocus();
    Navigator.of(context).pop(reason);
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Cancel this order?'),
      content: LpgTextField(
        label: 'Reason for cancelling',
        controller: _controller,
        autofocus: true,
        maxLines: 3,
        isRequired: true,
        hintText: 'For example: booked twice, no longer needed',
        errorText: _error,
        onChanged: (_) {
          if (_error != null) setState(() => _error = null);
        },
      ),
      actions: [
        LpgButton(
          label: 'Keep Order',
          variant: LpgButtonVariant.text,
          onPressed: _close,
        ),
        LpgButton(
          label: 'Cancel Order',
          variant: LpgButtonVariant.destructive,
          onPressed: () {
            final reason = _controller.text.trim();
            if (reason.isEmpty) {
              setState(() => _error = 'Please tell us why you are cancelling.');
              return;
            }
            _close(reason);
          },
        ),
      ],
    );
  }
}

/// Why the delivery failed (from the order's history) and what happens
/// next — the customer otherwise saw only a red "FAILED DELIVERY".
class _FailedDeliveryBanner extends ConsumerWidget {
  const _FailedDeliveryBanner({required this.orderId});

  final String orderId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final history = ref.watch(orderHistoryProvider(orderId)).asData?.value;
    String? reason;
    for (final entry in history ?? const <OrderStatusHistoryEntry>[]) {
      if (entry.toStatus == 'failed_delivery') reason = entry.reason;
    }
    return LpgBanner(
      tone: LpgTone.danger,
      title: 'Delivery attempt failed',
      message:
          '${reason != null ? 'Reason: $reason. ' : ''}'
          'Your agency will arrange another delivery. Need help sooner? '
          'Contact them from Support.',
      actionLabel: 'Get help',
      onAction: () => context.go('/support'),
    );
  }
}

/// One row per cylinder line: "Domestic 14.2kg × 2" with the unit price and
/// line total (CA-06).
class _LinesCard extends ConsumerWidget {
  const _LinesCard({required this.order});

  final OrderResponse order;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final names = ref.watch(cylinderTypeNamesProvider).asData?.value ?? {};
    final prices = _estimatedPrices(ref, order);
    return LpgCard(
      padding: const EdgeInsets.symmetric(vertical: LpgSpacing.xs),
      child: Column(
        children: [
          for (var i = 0; i < order.lines.length; i++) ...[
            if (i > 0) const Divider(indent: LpgSpacing.md),
            _lineTile(context, order.lines[i], names, prices),
          ],
        ],
      ),
    );
  }

  Widget _lineTile(
    BuildContext context,
    OrderLineResponse line,
    Map<String, String> names,
    Map<String, double> prices,
  ) {
    final unit = line.unitPrice ?? prices[line.cylinderTypeId];
    final details = [
      if (unit != null)
        '${LpgFormat.currency(unit)} each'
            '${line.unitPrice == null ? ' (estimated)' : ''}',
      if (line.quantityDelivered > 0) '${line.quantityDelivered} delivered',
      if (line.isBackordered) 'backordered',
    ];
    return LpgListTile(
      leadingIcon: LpgIcons.cylinder,
      title:
          '${names[line.cylinderTypeId] ?? 'LPG cylinder'} × '
          '${line.quantityOrdered}',
      subtitle: details.isEmpty ? null : details.join(' · '),
      trailing: unit != null
          ? Text(
              LpgFormat.currency(unit * line.quantityOrdered),
              style: context.lpgText.titleSmall,
            )
          : null,
    );
  }
}

/// Today's price per cylinder type for this customer, used to estimate an
/// order the agency hasn't confirmed (and priced) yet.
Map<String, double> _estimatedPrices(WidgetRef ref, OrderResponse order) {
  if (order.totalAmount != null || order.status == 'cancelled') return {};
  final orderable = ref.watch(orderableCylinderTypesProvider).asData?.value;
  return {
    for (final t in orderable ?? const <OrderableCylinderTypeResponse>[])
      t.cylinderTypeId: t.unitPrice,
  };
}

/// The total, or an estimate from today's prices until the agency confirms
/// the order — instead of "Pending" with no number at all (CA-06).
class _TotalCard extends ConsumerWidget {
  const _TotalCard({required this.order});

  final OrderResponse order;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final total = order.totalAmount;
    final String label;
    final String value;
    String? note;
    if (total != null) {
      label = 'Total Amount';
      value = LpgFormat.currency(total);
    } else if (order.status == 'cancelled') {
      label = 'Total Amount';
      value = 'Not charged';
    } else {
      final prices = _estimatedPrices(ref, order);
      final known = order.lines.every(
        (l) => prices.containsKey(l.cylinderTypeId),
      );
      label = 'Estimated total';
      value = known
          ? LpgFormat.currency(
              order.lines.fold<double>(
                0,
                (sum, l) => sum + prices[l.cylinderTypeId]! * l.quantityOrdered,
              ),
            )
          : 'Set on confirmation';
      note = 'The final amount is fixed when your agency confirms the order.';
    }
    return LpgCard(
      variant: LpgCardVariant.tonal,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          LpgKeyValueRow(label: label, value: value, emphasize: true),
          if (note != null)
            Text(
              note,
              style: context.lpgText.bodySmall?.copyWith(
                color: context.lpgColors.textSecondary,
              ),
            ),
        ],
      ),
    );
  }
}

/// After delivery: the order's invoice, and booking the same again.
class _DeliveredActions extends ConsumerWidget {
  const _DeliveredActions({required this.order});

  final OrderResponse order;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    InvoiceResponse? invoice;
    for (final i in ref.watch(invoicesProvider).asData?.value ?? const []) {
      if (i.orderId == order.id) invoice = i;
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (invoice case final invoice?) ...[
          LpgButton(
            label: 'View Invoice',
            icon: LpgIcons.invoice,
            variant: LpgButtonVariant.secondary,
            expand: true,
            onPressed: () =>
                context.push('/orders/invoices/${invoice.invoiceId}'),
          ),
          const SizedBox(height: LpgSpacing.smd),
        ],
        if (order.lines.isNotEmpty)
          LpgButton(
            label: 'Order Again',
            icon: LpgIcons.refill,
            expand: true,
            onPressed: () => context.push(
              '/orders/new',
              extra: ReorderDraft(
                cylinderTypeId: order.lines.first.cylinderTypeId,
                quantity: order.lines.first.quantityOrdered,
              ),
            ),
          ),
      ],
    );
  }
}

class _SummaryCard extends StatelessWidget {
  const _SummaryCard({required this.order});

  final OrderResponse order;

  @override
  Widget build(BuildContext context) {
    return LpgCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              LpgIconBox(
                icon: order.statusIcon,
                tone: order.statusSeverity.tone,
              ),
              const SizedBox(width: LpgSpacing.smd),
              Expanded(
                child: Text(order.reference, style: context.lpgText.titleLarge),
              ),
            ],
          ),
          const SizedBox(height: LpgSpacing.md),
          LpgStatusBadge(
            label: order.statusLabel,
            severity: order.statusSeverity,
          ),
          const SizedBox(height: LpgSpacing.smd),
          LpgKeyValueRow(
            icon: LpgIcons.calendar,
            label: 'Requested for',
            value: LpgFormat.date(order.requestedDate),
          ),
          LpgKeyValueRow(
            icon: LpgIcons.cylinder,
            label: 'Cylinders',
            value: '${order.cylinderCount}',
          ),
          if (order.paymentMethodPreference case final method?)
            LpgKeyValueRow(
              icon: LpgIcons.wallet,
              label: 'Paying by',
              value: paymentMethodLabel(method),
            ),
        ],
      ),
    );
  }
}
