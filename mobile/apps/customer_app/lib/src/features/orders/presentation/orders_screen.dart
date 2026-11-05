import 'package:api_client/api_client.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../data/orders_provider.dart';
import 'order_detail_screen.dart';
import 'order_presentation.dart';

class OrdersScreen extends ConsumerStatefulWidget {
  const OrdersScreen({super.key});

  @override
  ConsumerState<OrdersScreen> createState() => _OrdersScreenState();
}

class _OrdersScreenState extends ConsumerState<OrdersScreen> {
  String _filter = 'all';

  @override
  Widget build(BuildContext context) {
    final ordersAsync = ref.watch(ordersProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('My Orders'),
        actions: [
          IconButton(
            tooltip: 'Invoices',
            icon: const Icon(LpgIcons.invoice),
            onPressed: () => context.push('/orders/invoices'),
          ),
          const SizedBox(width: LpgSpacing.sm),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        heroTag: 'new-order',
        onPressed: () => context.push('/orders/new'),
        icon: const Icon(LpgIcons.add),
        label: const Text('New order'),
      ),
      body: LpgMasterDetail(
        emptyMessage: 'Select an order from the list to view full details and tracking.',
        emptyIcon: LpgIcons.orders,
        masterBuilder: (context, controller) {
          return ordersAsync.when(
            loading: () => const LpgSkeletonList(),
            error: (err, stack) => LpgErrorState(
              message: 'Failed to load orders\n${err.toString()}',
              onRetry: () => ref.refresh(ordersProvider),
            ),
            data: (orders) {
              if (orders.isEmpty) {
                return LpgEmptyState(
                  title: 'No orders yet',
                  message: 'Book your first refill and track it right here.',
                  icon: LpgIcons.orders,
                  actionLabel: 'Book Cylinder',
                  actionIcon: LpgIcons.refill,
                  onAction: () => context.push('/orders/new'),
                );
              }

              final activeOrders = orders.where((o) => o.isTrackable).toList();
              final completedOrders = orders.where((o) => !o.isTrackable).toList();

              final filteredOrders = switch (_filter) {
                'active' => activeOrders,
                'completed' => completedOrders,
                _ => orders,
              };

              return RefreshIndicator(
                onRefresh: () async => ref.refresh(ordersProvider.future),
                child: ListView(
                  padding: LpgSpacing.page.copyWith(
                    bottom: LpgSizes.touchTarget * 2,
                  ),
                  children: [
                    LpgSegmentedControl<String>(
                      selectedValue: _filter,
                      onValueChanged: (val) => setState(() => _filter = val),
                      segments: [
                        LpgSegmentItem(
                          value: 'all',
                          label: 'All',
                          badgeCount: orders.length,
                        ),
                        LpgSegmentItem(
                          value: 'active',
                          label: 'Active',
                          badgeCount: activeOrders.length,
                        ),
                        LpgSegmentItem(
                          value: 'completed',
                          label: 'History',
                          badgeCount: completedOrders.length,
                        ),
                      ],
                    ),
                    const SizedBox(height: LpgSpacing.md),

                    if (filteredOrders.isEmpty)
                      Padding(
                        padding: const EdgeInsets.only(top: LpgSpacing.xl),
                        child: LpgEmptyState(
                          message: 'No ${_filter == "active" ? "active" : "past"} orders match your filter.',
                          icon: LpgIcons.filter,
                        ),
                      )
                    else
                      LpgGroupedList(
                        children: [
                          for (final order in filteredOrders)
                            LpgListTile(
                              selected: controller.selectedId == order.id,
                              leadingIcon: order.statusIcon,
                              leadingTone: order.statusSeverity.tone,
                              title: order.reference,
                              subtitle:
                                  '${order.statusLabel}  ·  ${order.cylinderCount} '
                                  '${order.cylinderCount == 1 ? 'cylinder' : 'cylinders'}',
                              trailing: order.isTrackable
                                  ? LpgButton(
                                      label: 'Track',
                                      icon: LpgIcons.navigate,
                                      variant: LpgButtonVariant.text,
                                      onPressed: () {
                                        if (!controller.open(order.id)) {
                                          context.push('/orders/${order.id}/track');
                                        }
                                      },
                                    )
                                  : Text(
                                      LpgFormat.shortDate(order.requestedDate),
                                      style: context.lpgText.bodySmall,
                                    ),
                              showChevron: !order.isTrackable && !controller.twoPane,
                              onTap: () {
                                if (!controller.open(order.id)) {
                                  context.push('/orders/${order.id}');
                                }
                              },
                            ),
                        ],
                      ),
                  ],
                ),
              );
            },
          );
        },
        detailBuilder: (context, id) {
          return OrderDetailScreen(orderId: id);
        },
      ),
    );
  }
}
