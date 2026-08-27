import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import '../data/orders_provider.dart';
import 'order_bottom_sheet.dart';

class OrdersScreen extends ConsumerWidget {
  const OrdersScreen({super.key});

  void _showOrderSheet(BuildContext context) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (context) => const OrderBottomSheet(),
    );
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final ordersAsync = ref.watch(ordersProvider);
    final colors = Theme.of(context).extension<LpgColors>()!;
    final theme = Theme.of(context);

    return Scaffold(
      backgroundColor: theme.scaffoldBackgroundColor,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        centerTitle: true,
        title: Text(
          'My Orders',
          style: theme.textTheme.titleMedium?.copyWith(
            fontWeight: FontWeight.w600,
            color: colors.textPrimary,
          ),
        ),
        actions: [
          IconButton(
            icon: Icon(Icons.receipt_outlined, color: colors.textPrimary),
            onPressed: () => context.push('/orders/invoices'),
          ),
        ],
      ),
      body: ordersAsync.when(
        loading: () => const Center(child: LpgLoadingIndicator()),
        error: (err, stack) => LpgEmptyState(
          message: 'Failed to load orders\n${err.toString()}',
          icon: Icons.error_outline,
          actionLabel: 'Retry',
          onAction: () => ref.refresh(ordersProvider),
        ),
        data: (orders) {
          if (orders.isEmpty) {
            return LpgEmptyState(
              message: 'No orders yet',
              icon: Icons.receipt_long_outlined,
              actionLabel: 'Book Cylinder',
              onAction: () => _showOrderSheet(context),
            );
          }

          return RefreshIndicator(
            onRefresh: () async => ref.refresh(ordersProvider.future),
            child: ListView.separated(
              padding: const EdgeInsets.all(16.0),
              itemCount: orders.length,
              separatorBuilder: (context, index) => const SizedBox(height: 12),
              itemBuilder: (context, index) {
                final order = orders[index];

                final severity = switch (order.status) {
                  'delivered' => LpgStatusSeverity.success,
                  'cancelled' || 'failed_delivery' => LpgStatusSeverity.danger,
                  'out_for_delivery' ||
                  'ready_for_dispatch' => LpgStatusSeverity.warning,
                  _ => LpgStatusSeverity.info,
                };

                return LpgCard(
                  onTap: () => context.push('/orders/${order.id}'),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Text(
                            'Order #${order.id.substring(0, 8).toUpperCase()}',
                            style: theme.textTheme.titleSmall?.copyWith(
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
                      const SizedBox(height: 12),
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
                      const SizedBox(height: 16),
                      Divider(height: 1, color: colors.borderDefault),
                      const SizedBox(height: 16),
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                'Amount',
                                style: theme.textTheme.labelSmall?.copyWith(
                                  color: colors.textSecondary,
                                ),
                              ),
                              const SizedBox(height: 2),
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
                          if (order.status == 'out_for_delivery')
                            LpgButton(
                              label: 'Track',
                              onPressed: () =>
                                  context.push('/orders/${order.id}/track'),
                              icon: Icons.location_on_outlined,
                            )
                          else
                            LpgButton(
                              label: 'Details',
                              onPressed: () =>
                                  context.push('/orders/${order.id}'),
                              variant: LpgButtonVariant.text,
                            ),
                        ],
                      ),
                    ],
                  ),
                );
              },
            ),
          );
        },
      ),
    );
  }
}
