import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../data/orders_provider.dart';
import 'order_presentation.dart';

class OrdersScreen extends ConsumerWidget {
  const OrdersScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
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
      body: ordersAsync.when(
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

          return RefreshIndicator(
            onRefresh: () async => ref.refresh(ordersProvider.future),
            child: ListView(
              // Bottom padding clears the floating "New order" button.
              padding: LpgSpacing.page.copyWith(
                bottom: LpgSizes.touchTarget * 2,
              ),
              children: [
                LpgGroupedList(
                  children: [
                    for (final order in orders)
                      LpgListTile(
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
                                onPressed: () =>
                                    context.push('/orders/${order.id}/track'),
                              )
                            : Text(
                                LpgFormat.shortDate(order.requestedDate),
                                style: context.lpgText.bodySmall,
                              ),
                        showChevron: !order.isTrackable,
                        onTap: () => context.push('/orders/${order.id}'),
                      ),
                  ],
                ),
              ],
            ),
          );
        },
      ),
    );
  }
}
