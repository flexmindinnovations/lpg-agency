import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../data/orders_provider.dart';

class OrdersScreen extends ConsumerWidget {
  const OrdersScreen({super.key});

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
      ),
      body: ordersAsync.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (err, stack) => Center(
          child: Padding(
            padding: const EdgeInsets.all(24.0),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(Icons.error_outline, size: 48, color: colors.statusDanger),
                const SizedBox(height: 16),
                Text(
                  'Failed to load orders',
                  style: theme.textTheme.titleMedium,
                ),
                const SizedBox(height: 8),
                Text(
                  err.toString(),
                  textAlign: TextAlign.center,
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: colors.textSecondary,
                  ),
                ),
                const SizedBox(height: 24),
                ElevatedButton(
                  onPressed: () => ref.refresh(ordersProvider),
                  child: const Text('Retry'),
                ),
              ],
            ),
          ),
        ),
        data: (orders) {
          if (orders.isEmpty) {
            return Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(
                    Icons.receipt_long_outlined,
                    size: 64,
                    color: colors.textSecondary.withOpacity(0.5),
                  ),
                  const SizedBox(height: 16),
                  Text(
                    'No orders yet',
                    style: theme.textTheme.titleMedium?.copyWith(
                      color: colors.textSecondary,
                    ),
                  ),
                  const SizedBox(height: 24),
                  ElevatedButton(
                    onPressed: () {},
                    child: const Text('Book Cylinder'),
                  ),
                ],
              ),
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
                final isCompleted = order.status == 'delivered';
                final isCancelled = order.status == 'cancelled' || order.status == 'failed_delivery';
                
                final statusColor = isCompleted
                    ? colors.statusSuccess
                    : (isCancelled ? colors.statusDanger : colors.actionPrimary);

                return Card(
                  elevation: 0,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(16),
                    side: BorderSide(color: colors.borderDefault),
                  ),
                  color: colors.surfaceRaised,
                  child: InkWell(
                    borderRadius: BorderRadius.circular(16),
                    onTap: () {
                      // Navigate to order details / tracking
                    },
                    child: Padding(
                      padding: const EdgeInsets.all(16.0),
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
                              Container(
                                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                                decoration: BoxDecoration(
                                  color: statusColor.withOpacity(0.1),
                                  borderRadius: BorderRadius.circular(8),
                                ),
                                child: Text(
                                  order.status.replaceAll('_', ' ').toUpperCase(),
                                  style: theme.textTheme.labelSmall?.copyWith(
                                    color: statusColor,
                                    fontWeight: FontWeight.w600,
                                  ),
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 12),
                          Row(
                            children: [
                              Icon(Icons.calendar_today_outlined, size: 16, color: colors.textSecondary),
                              const SizedBox(width: 8),
                              Text(
                                DateFormat('MMM dd, yyyy • hh:mm a').format(order.requestedDate),
                                style: theme.textTheme.bodySmall?.copyWith(
                                  color: colors.textSecondary,
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 16),
                          const Divider(height: 1),
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
                                ElevatedButton.icon(
                                  onPressed: () {},
                                  icon: const Icon(Icons.location_on_outlined, size: 16),
                                  label: const Text('Track Order'),
                                  style: ElevatedButton.styleFrom(
                                    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                                    textStyle: theme.textTheme.labelLarge?.copyWith(
                                      fontWeight: FontWeight.w600,
                                    ),
                                  ),
                                )
                              else
                                TextButton(
                                  onPressed: () {},
                                  child: const Text('View Details'),
                                ),
                            ],
                          ),
                        ],
                      ),
                    ),
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
