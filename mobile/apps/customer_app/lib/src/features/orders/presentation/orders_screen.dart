import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../data/orders_provider.dart';
import 'order_presentation.dart';

class OrdersScreen extends ConsumerStatefulWidget {
  const OrdersScreen({super.key});

  @override
  ConsumerState<OrdersScreen> createState() => _OrdersScreenState();
}

class _OrdersScreenState extends ConsumerState<OrdersScreen> {
  final _searchController = TextEditingController();
  String _query = '';

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

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

          final q = _query.trim().toLowerCase();
          final shown = q.isEmpty
              ? orders
              : orders
                    .where(
                      (o) =>
                          o.reference.toLowerCase().contains(q) ||
                          o.statusLabel.toLowerCase().contains(q) ||
                          LpgFormat.shortDate(
                            o.requestedDate,
                          ).toLowerCase().contains(q),
                    )
                    .toList();

          return RefreshIndicator(
            onRefresh: () async => ref.refresh(ordersProvider.future),
            child: ListView(
              // Bottom padding clears the floating "New order" button.
              padding: LpgSpacing.page.copyWith(
                bottom: LpgSizes.touchTarget * 2,
              ),
              children: [
                TextField(
                  controller: _searchController,
                  onChanged: (v) => setState(() => _query = v),
                  textInputAction: TextInputAction.search,
                  decoration: InputDecoration(
                    hintText: 'Search by order number, status or date',
                    prefixIcon: const Icon(LpgIcons.search),
                    suffixIcon: _query.isEmpty
                        ? null
                        : IconButton(
                            tooltip: 'Clear search',
                            icon: const Icon(LpgIcons.close),
                            onPressed: () {
                              _searchController.clear();
                              setState(() => _query = '');
                            },
                          ),
                  ),
                ),
                const SizedBox(height: LpgSpacing.md),
                if (shown.isEmpty)
                  const Padding(
                    padding: EdgeInsets.symmetric(vertical: LpgSpacing.xl),
                    child: Center(child: Text('No orders match your search.')),
                  ),
                LpgGroupedList(
                  children: [
                    for (final order in shown)
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
                        showChevron: true,
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
