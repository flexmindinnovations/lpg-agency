import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../data/orders_provider.dart';

class OrderTrackingScreen extends ConsumerWidget {
  const OrderTrackingScreen({super.key, required this.orderId});

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
          'Track Order',
          style: theme.textTheme.titleMedium?.copyWith(
            fontWeight: FontWeight.w600,
            color: colors.textPrimary,
          ),
        ),
      ),
      body: orderAsync.when(
        loading: () => const Center(child: LpgLoadingIndicator()),
        error: (err, _) => LpgEmptyState(
          message: 'Failed to load order tracking: $err',
          icon: Icons.error_outline,
          actionLabel: 'Retry',
          onAction: () => ref.refresh(orderDetailProvider(orderId)),
        ),
        data: (order) {
          final status = order.status;

          return Column(
            children: [
              // Map Placeholder
              Expanded(
                flex: 3,
                child: Container(
                  width: double.infinity,
                  color: colors.surfaceOverlay,
                  child: Stack(
                    children: [
                      Center(
                        child: Column(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Icon(
                              Icons.map_outlined,
                              size: 64,
                              color: colors.textSecondary.withValues(
                                alpha: 0.3,
                              ),
                            ),
                            const SizedBox(height: 16),
                            Text(
                              status == 'out_for_delivery'
                                  ? 'Driver is on the way'
                                  : 'Map available when out for delivery',
                              style: theme.textTheme.bodyMedium?.copyWith(
                                color: colors.textSecondary,
                              ),
                            ),
                          ],
                        ),
                      ),
                      if (status == 'out_for_delivery')
                        Positioned(
                          top: 100,
                          left: 150,
                          child: Container(
                            padding: const EdgeInsets.all(8),
                            decoration: BoxDecoration(
                              color: colors.actionPrimary,
                              shape: BoxShape.circle,
                              boxShadow: [
                                BoxShadow(
                                  color: colors.actionPrimary.withValues(
                                    alpha: 0.3,
                                  ),
                                  blurRadius: 12,
                                  spreadRadius: 4,
                                ),
                              ],
                            ),
                            child: const Icon(
                              Icons.local_shipping,
                              color: Colors.white,
                              size: 24,
                            ),
                          ),
                        ),
                    ],
                  ),
                ),
              ),

              // Order Milestones
              Expanded(
                flex: 4,
                child: Container(
                  padding: const EdgeInsets.all(24),
                  decoration: BoxDecoration(
                    color: colors.surfaceBase,
                    borderRadius: const BorderRadius.vertical(
                      top: Radius.circular(32),
                    ),
                    boxShadow: [
                      BoxShadow(
                        color: Colors.black.withValues(alpha: 0.05),
                        blurRadius: 20,
                        offset: const Offset(0, -5),
                      ),
                    ],
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                'Order Status',
                                style: theme.textTheme.labelSmall?.copyWith(
                                  color: colors.textSecondary,
                                ),
                              ),
                              Text(
                                status.replaceAll('_', ' ').toUpperCase(),
                                style: theme.textTheme.titleMedium?.copyWith(
                                  fontWeight: FontWeight.bold,
                                  color: colors.textPrimary,
                                ),
                              ),
                            ],
                          ),
                          LpgStatusBadge(
                            label: status.replaceAll('_', ' ').toUpperCase(),
                            severity: _getSeverity(status),
                          ),
                        ],
                      ),
                      const SizedBox(height: 32),
                      Expanded(
                        child: ListView(
                          children: [
                            _buildMilestone(
                              context,
                              title: 'Order Placed',
                              time: 'Completed',
                              isCompleted: true,
                              isLast: false,
                            ),
                            _buildMilestone(
                              context,
                              title: 'Confirmed by Agency',
                              time: status != 'booked'
                                  ? 'Completed'
                                  : 'Pending',
                              isCompleted: status != 'booked',
                              isLast: false,
                              isCurrent: status == 'confirmed',
                            ),
                            _buildMilestone(
                              context,
                              title: 'Out for Delivery',
                              time:
                                  status == 'out_for_delivery' ||
                                      status == 'delivered'
                                  ? 'In Progress'
                                  : 'Pending',
                              isCompleted:
                                  status == 'out_for_delivery' ||
                                  status == 'delivered',
                              isLast: false,
                              isCurrent: status == 'out_for_delivery',
                            ),
                            _buildMilestone(
                              context,
                              title: 'Delivered',
                              time: status == 'delivered'
                                  ? 'Completed'
                                  : 'Pending',
                              isCompleted: status == 'delivered',
                              isLast: true,
                              isCurrent: status == 'delivered',
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ],
          );
        },
      ),
    );
  }

  LpgStatusSeverity _getSeverity(String status) {
    return switch (status) {
      'delivered' => LpgStatusSeverity.success,
      'cancelled' || 'failed_delivery' => LpgStatusSeverity.danger,
      'out_for_delivery' || 'ready_for_dispatch' => LpgStatusSeverity.warning,
      _ => LpgStatusSeverity.info,
    };
  }

  Widget _buildMilestone(
    BuildContext context, {
    required String title,
    required String time,
    required bool isCompleted,
    required bool isLast,
    bool isCurrent = false,
  }) {
    final colors = Theme.of(context).extension<LpgColors>()!;
    final theme = Theme.of(context);

    return IntrinsicHeight(
      child: Row(
        children: [
          Column(
            children: [
              Container(
                width: 24,
                height: 24,
                decoration: BoxDecoration(
                  color: colors.surfaceRaised,
                  shape: BoxShape.circle,
                  border: Border.all(
                    color: isCompleted
                        ? colors.actionPrimary
                        : colors.borderDefault,
                  ),
                ),
                child: Center(
                  child: Container(
                    width: 8,
                    height: 8,
                    decoration: BoxDecoration(
                      color: isCompleted
                          ? colors.actionPrimary
                          : colors.borderStrong,
                      shape: BoxShape.circle,
                    ),
                  ),
                ),
              ),
              if (!isLast)
                Expanded(
                  child: Container(
                    width: 2,
                    margin: const EdgeInsets.symmetric(vertical: 4),
                    color: isCompleted
                        ? colors.actionPrimary
                        : colors.borderDefault,
                  ),
                ),
            ],
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Padding(
              padding: const EdgeInsets.only(bottom: 24),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: theme.textTheme.bodyMedium?.copyWith(
                      fontWeight: isCurrent
                          ? FontWeight.bold
                          : FontWeight.normal,
                      color: isCompleted
                          ? colors.textPrimary
                          : colors.textSecondary,
                    ),
                  ),
                  Text(
                    time,
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: colors.textSecondary,
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
