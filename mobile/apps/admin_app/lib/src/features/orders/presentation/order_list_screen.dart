// Order List Screen for Admin App
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../data/orders_provider.dart';

class OrderListScreen extends ConsumerStatefulWidget {
  const OrderListScreen({super.key});

  @override
  ConsumerState<OrderListScreen> createState() => _OrderListScreenState();
}

class _OrderListScreenState extends ConsumerState<OrderListScreen> {
  String _selectedFilter = 'ALL';

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;
    final text = context.lpgText;

    final ordersAsync = ref.watch(adminOrdersProvider(1));

    return Scaffold(
      appBar: AppBar(
        title: const Text('Order Management'),
        actions: [
          IconButton(
            icon: const Icon(LpgIcons.orders),
            onPressed: () => ref.invalidate(adminOrdersProvider(1)),
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => context.goNamed('order_new'),
        icon: const Icon(Icons.add),
        label: const Text('New Order'),
      ),
      body: Column(
        children: [
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.symmetric(horizontal: LpgSpacing.md, vertical: LpgSpacing.sm),
            child: Row(
              children: [
                'ALL',
                'PENDING',
                'ASSIGNED',
                'OUT_FOR_DELIVERY',
                'DELIVERED',
                'CANCELLED'
              ].map((status) {
                final selected = _selectedFilter == status;
                return Padding(
                  padding: const EdgeInsets.only(right: LpgSpacing.xs),
                  child: FilterChip(
                    label: Text(status.replaceAll('_', ' ')),
                    selected: selected,
                    onSelected: (_) => setState(() => _selectedFilter = status),
                  ),
                );
              }).toList(),
            ),
          ),
          Expanded(
            child: ordersAsync.when(
              loading: () => const LpgSkeletonList(itemCount: 5),
              error: (err, _) => LpgErrorState(
                message: 'Failed to load orders: $err',
                onRetry: () => ref.invalidate(adminOrdersProvider(1)),
              ),
              data: (page) {
                final orders = page.items.where((o) {
                  if (_selectedFilter == 'ALL') return true;
                  return o.status.toUpperCase() == _selectedFilter;
                }).toList();

                if (orders.isEmpty) {
                  return const LpgEmptyState(
                    message: 'No orders match the selected filter.',
                    icon: LpgIcons.orders,
                  );
                }

                return ListView.separated(
                  padding: LpgSpacing.page,
                  itemCount: orders.length,
                  separatorBuilder: (_, _) => const SizedBox(height: LpgSpacing.sm),
                  itemBuilder: (context, index) {
                    final order = orders[index];
                    return LpgCard(
                      onTap: () => context.goNamed('order_detail', pathParameters: {'orderId': order.id}),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            mainAxisAlignment: MainAxisAlignment.spaceBetween,
                            children: [
                              Text(order.orderNumber ?? order.id.substring(0, 8), style: text.titleMedium),
                              LpgStatusBadge(
                                label: order.status,
                                severity: switch (order.status.toLowerCase()) {
                                  'delivered' => LpgStatusSeverity.success,
                                  'cancelled' => LpgStatusSeverity.danger,
                                  'out_for_delivery' => LpgStatusSeverity.info,
                                  _ => LpgStatusSeverity.warning,
                                },
                              ),
                            ],
                          ),
                          const SizedBox(height: LpgSpacing.xs),
                          Text(
                            'Customer: ${order.customerId}',
                            style: text.bodyMedium?.copyWith(color: colors.textSecondary),
                          ),
                          const SizedBox(height: LpgSpacing.xs),
                          Row(
                            mainAxisAlignment: MainAxisAlignment.spaceBetween,
                            children: [
                              Text(
                                LpgFormat.date(order.requestedDate),
                                style: text.bodySmall?.copyWith(color: colors.textSecondary),
                              ),
                              Text(
                                LpgFormat.currency(order.totalAmount ?? 0.0),
                                style: text.titleSmall?.copyWith(color: colors.actionPrimary),
                              ),
                            ],
                          ),
                        ],
                      ),
                    );
                  },
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}
