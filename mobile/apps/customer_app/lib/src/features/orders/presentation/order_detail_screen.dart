import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import '../../../providers.dart';
import '../data/orders_provider.dart';

/// Statuses a customer can no longer cancel from — already dispatched or
/// resolved one way or another. `OrderApi.cancelOrder` still accepts a
/// cancel request past this point (the backend answers with
/// `pendingApproval: true` for a post-dispatch cancel per D-19), but there's
/// no real path back from `delivered`/`cancelled`/`failed_delivery`.
const _terminalStatuses = {'delivered', 'cancelled', 'failed_delivery'};

class OrderDetailScreen extends ConsumerWidget {
  const OrderDetailScreen({super.key, required this.orderId});

  final String orderId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final orderAsync = ref.watch(orderDetailProvider(orderId));
    final colors = Theme.of(context).extension<LpgColors>()!;
    final theme = Theme.of(context);

    return Scaffold(
      backgroundColor: theme.scaffoldBackgroundColor,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        centerTitle: true,
        title: Text(
          'Order Details',
          style: theme.textTheme.titleMedium?.copyWith(
            fontWeight: FontWeight.w600,
            color: colors.textPrimary,
          ),
        ),
      ),
      body: orderAsync.when(
        loading: () => const Center(child: LpgLoadingIndicator()),
        error: (err, _) => LpgEmptyState(
          message: 'Failed to load this order\n$err',
          icon: Icons.error_outline,
          actionLabel: 'Retry',
          onAction: () => ref.refresh(orderDetailProvider(orderId)),
        ),
        data: (order) {
          final severity = switch (order.status) {
            'delivered' => LpgStatusSeverity.success,
            'cancelled' || 'failed_delivery' => LpgStatusSeverity.danger,
            'out_for_delivery' ||
            'ready_for_dispatch' => LpgStatusSeverity.warning,
            _ => LpgStatusSeverity.info,
          };
          final cancellable = !_terminalStatuses.contains(order.status);

          return ListView(
            padding: const EdgeInsets.all(24.0),
            children: [
              LpgCard(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Text(
                          'Order #${order.id.substring(0, 8).toUpperCase()}',
                          style: theme.textTheme.titleLarge?.copyWith(
                            fontWeight: FontWeight.bold,
                            color: colors.textPrimary,
                          ),
                        ),
                        LpgStatusBadge(
                          label: order.status
                              .replaceAll('_', ' ')
                              .toUpperCase(),
                          severity: severity,
                        ),
                      ],
                    ),
                    const SizedBox(height: 8),
                    Row(
                      children: [
                        Icon(
                          Icons.calendar_today_outlined,
                          size: 16,
                          color: colors.textSecondary,
                        ),
                        const SizedBox(width: 8),
                        Text(
                          DateFormat(
                            'MMM dd, yyyy • hh:mm a',
                          ).format(order.requestedDate),
                          style: theme.textTheme.bodySmall?.copyWith(
                            color: colors.textSecondary,
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),

              const SizedBox(height: 24),
              Text(
                'Delivery Address',
                style: theme.textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.w600,
                  color: colors.textPrimary,
                ),
              ),
              const SizedBox(height: 12),
              LpgCard(
                child: Row(
                  children: [
                    Icon(
                      Icons.location_on_outlined,
                      color: colors.actionPrimary,
                    ),
                    const SizedBox(width: 16),
                    Expanded(
                      child: Text(
                        order.deliveryAddress.addressLine,
                        style: theme.textTheme.bodyMedium?.copyWith(
                          color: colors.textPrimary,
                        ),
                      ),
                    ),
                  ],
                ),
              ),

              const SizedBox(height: 24),
              Text(
                'Cylinders',
                style: theme.textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.w600,
                  color: colors.textPrimary,
                ),
              ),
              const SizedBox(height: 12),
              LpgCard(
                padding: EdgeInsets.zero,
                child: Column(
                  children: [
                    for (var i = 0; i < order.lines.length; i++) ...[
                      if (i > 0)
                        Divider(
                          height: 1,
                          indent: 16,
                          color: colors.borderDefault,
                        ),
                      LpgListTile(
                        leadingIcon: Icons.local_gas_station_outlined,
                        title:
                            'Qty ${order.lines[i].quantityOrdered}'
                            '${order.lines[i].isBackordered ? ' (backordered)' : ''}',
                        subtitle: order.lines[i].quantityDelivered > 0
                            ? '${order.lines[i].quantityDelivered} delivered'
                            : null,
                        trailing: order.lines[i].unitPrice != null
                            ? Text(
                                '₹${order.lines[i].unitPrice!.toStringAsFixed(2)}',
                                style: theme.textTheme.bodyMedium?.copyWith(
                                  fontWeight: FontWeight.w600,
                                  color: colors.textPrimary,
                                ),
                              )
                            : null,
                      ),
                    ],
                  ],
                ),
              ),

              const SizedBox(height: 24),
              LpgCard(
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(
                      'Total Amount',
                      style: theme.textTheme.bodyMedium?.copyWith(
                        color: colors.textSecondary,
                      ),
                    ),
                    Text(
                      order.totalAmount != null
                          ? '₹${order.totalAmount!.toStringAsFixed(2)}'
                          : 'Pending',
                      style: theme.textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.bold,
                        color: colors.textPrimary,
                      ),
                    ),
                  ],
                ),
              ),

              const SizedBox(height: 32),
              if (order.status == 'out_for_delivery')
                LpgButton(
                  label: 'Track Delivery',
                  icon: Icons.location_on_outlined,
                  expand: true,
                  onPressed: () => context.push('/orders/$orderId/track'),
                ),
              if (cancellable) ...[
                if (order.status == 'out_for_delivery')
                  const SizedBox(height: 12),
                LpgButton(
                  label: 'Cancel Order',
                  variant: LpgButtonVariant.secondary,
                  expand: true,
                  onPressed: () => _confirmCancel(context, ref, order.status),
                ),
              ],
              const SizedBox(height: 24),
            ],
          );
        },
      ),
    );
  }

  Future<void> _confirmCancel(
    BuildContext context,
    WidgetRef ref,
    String currentStatus,
  ) async {
    final reasonController = TextEditingController();
    final reason = await showDialog<String>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Cancel this order?'),
        content: TextField(
          controller: reasonController,
          autofocus: true,
          maxLines: 3,
          decoration: const InputDecoration(
            hintText: 'Reason for cancellation',
          ),
        ),
        actions: [
          TextButton(
            onPressed: () {
              // Unfocus before popping: dismissing a route while its own
              // TextField is still IME-focused is a known trigger for a
              // framework-level `_dependents.isEmpty` assertion crash
              // (an InheritedElement torn down with a dependent still
              // registered, from the focus/keyboard-visibility rebuild
              // racing the pop's element teardown) — confirmed live on
              // this exact dialog.
              FocusScope.of(dialogContext).unfocus();
              Navigator.of(dialogContext).pop();
            },
            child: const Text('Keep Order'),
          ),
          TextButton(
            onPressed: () {
              final reason = reasonController.text.trim();
              if (reason.isEmpty) return;
              FocusScope.of(dialogContext).unfocus();
              Navigator.of(dialogContext).pop(reason);
            },
            child: const Text('Cancel Order'),
          ),
        ],
      ),
    );
    reasonController.dispose();

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
        messenger.showSnackBar(
          SnackBar(
            content: Text(
              response.pendingApproval
                  ? 'Cancellation requested — this order was already '
                        'dispatched, so a manager needs to approve it.'
                  : 'Order cancelled.',
            ),
          ),
        );
      },
      onFailure: (failure) => ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Could not cancel order: ${failure.message}')),
      ),
    );
  }
}
