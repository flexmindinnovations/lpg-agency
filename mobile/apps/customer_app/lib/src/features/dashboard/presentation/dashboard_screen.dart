import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import '../../orders/data/orders_provider.dart';
import '../../orders/presentation/order_bottom_sheet.dart';
import '../data/ledger_provider.dart';
import '../data/notifications_provider.dart';

/// The main dashboard for the Customer App.
///
/// Implements a stark, minimalist aesthetic inspired by modern apps (e.g. ChatGPT).
/// Focuses purely on the current balance and the primary action: ordering gas.
class DashboardScreen extends ConsumerWidget {
  const DashboardScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final colors = Theme.of(context).extension<LpgColors>()!;
    final theme = Theme.of(context);

    final ledgerAsync = ref.watch(ledgerProvider);
    final ordersAsync = ref.watch(ordersProvider);
    final unreadCountAsync = ref.watch(unreadNotificationCountProvider);

    return Scaffold(
      backgroundColor: theme.scaffoldBackgroundColor,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        centerTitle: true,
        title: Text(
          'LPG Flow',
          style: theme.textTheme.titleMedium?.copyWith(
            fontWeight: FontWeight.w600,
            color: colors.textPrimary,
          ),
        ),
        actions: [
          Stack(
            children: [
              IconButton(
                icon: Icon(
                  Icons.notifications_outlined,
                  color: colors.textPrimary,
                ),
                onPressed: () => context.push('/notifications'),
              ),
              unreadCountAsync.when(
                data: (count) => count > 0
                    ? Positioned(
                        right: 8,
                        top: 8,
                        child: Container(
                          padding: const EdgeInsets.all(4),
                          decoration: BoxDecoration(
                            color: colors.statusDanger,
                            shape: BoxShape.circle,
                            boxShadow: [
                              BoxShadow(
                                color: colors.statusDanger.withValues(
                                  alpha: 0.3,
                                ),
                                blurRadius: 4,
                                spreadRadius: 1,
                              ),
                            ],
                          ),
                          constraints: const BoxConstraints(
                            minWidth: 16,
                            minHeight: 16,
                          ),
                          child: Text(
                            '$count',
                            style: const TextStyle(
                              color: Colors.white,
                              fontSize: 9,
                              fontWeight: FontWeight.bold,
                            ),
                            textAlign: TextAlign.center,
                          ),
                        ),
                      )
                    : const SizedBox.shrink(),
                loading: () => const SizedBox.shrink(),
                error: (error, stack) => const SizedBox.shrink(),
              ),
            ],
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: () async {
          ref.invalidate(ledgerProvider);
          ref.invalidate(ordersProvider);
          ref.invalidate(unreadNotificationCountProvider);
        },
        child: SingleChildScrollView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.symmetric(horizontal: 24.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const SizedBox(height: 24),
              // Location Header
              Row(
                children: [
                  Icon(
                    Icons.location_on_outlined,
                    size: 16,
                    color: colors.textSecondary,
                  ),
                  const SizedBox(width: 8),
                  Text(
                    'PRIMARY ADDRESS',
                    style: theme.textTheme.labelSmall?.copyWith(
                      color: colors.textSecondary,
                      letterSpacing: 1.2,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 16),

              // Main Balance Card
              ledgerAsync.when(
                data: (ledger) {
                  final totalBalance =
                      ledger?.balances.fold<int>(
                        0,
                        (sum, item) => sum + item.quantity,
                      ) ??
                      0;
                  return LpgCard(
                    padding: const EdgeInsets.all(32),
                    child: Column(
                      children: [
                        Text(
                          'Outstanding Empty Cylinders',
                          style: theme.textTheme.bodyMedium?.copyWith(
                            color: colors.textSecondary,
                          ),
                        ),
                        const SizedBox(height: 16),
                        Text(
                          '$totalBalance',
                          style: theme.textTheme.displayMedium?.copyWith(
                            fontWeight: FontWeight.w700,
                            color: colors.textPrimary,
                          ),
                        ),
                        const SizedBox(height: 16),
                        Text(
                          ledger != null && ledger.balances.isNotEmpty
                              ? 'Across ${ledger.balances.length} cylinder types'
                              : 'No outstanding cylinders',
                          style: theme.textTheme.bodySmall?.copyWith(
                            color: colors.textSecondary,
                          ),
                        ),
                      ],
                    ),
                  );
                },
                loading: () => const LpgCard(
                  padding: EdgeInsets.all(32),
                  child: Center(child: LpgLoadingIndicator()),
                ),
                error: (err, _) => LpgCard(
                  padding: const EdgeInsets.all(32),
                  child: Text('Failed to load balance: $err'),
                ),
              ),

              const SizedBox(height: 32),

              // Primary Action Button (Pill shaped)
              LpgButton(
                label: 'Order Gas Refill',
                onPressed: () => _showOrderSheet(context),
                icon: Icons.local_gas_station_outlined,
                expand: true,
              ),

              const SizedBox(height: 48),

              // Recent Activity Section
              Text(
                'Recent Orders',
                style: theme.textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.w600,
                  color: colors.textPrimary,
                ),
              ),
              const SizedBox(height: 16),

              ordersAsync.when(
                data: (orders) {
                  if (orders.isEmpty) {
                    return Text(
                      'No recent orders',
                      style: theme.textTheme.bodyMedium?.copyWith(
                        color: colors.textSecondary,
                      ),
                    );
                  }
                  final recentOrders = orders.take(3).toList();
                  return Column(
                    children: recentOrders.map((order) {
                      return Padding(
                        padding: const EdgeInsets.only(bottom: 8.0),
                        child: LpgListTile(
                          leadingIcon: Icons.receipt_long_outlined,
                          title:
                              'Order #${order.id.substring(0, 8).toUpperCase()}',
                          subtitle: order.status
                              .replaceAll('_', ' ')
                              .toUpperCase(),
                          trailing: Text(
                            DateFormat('MMM dd').format(order.requestedDate),
                            style: theme.textTheme.bodySmall?.copyWith(
                              color: colors.textSecondary,
                            ),
                          ),
                          onTap: () => context.push('/orders'),
                        ),
                      );
                    }).toList(),
                  );
                },
                loading: () => const Center(child: LpgLoadingIndicator()),
                error: (error, stack) =>
                    const Text('Failed to load recent orders'),
              ),
            ],
          ),
        ),
      ),
    );
  }

  void _showOrderSheet(BuildContext context) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (context) => const OrderBottomSheet(),
    );
  }
}
