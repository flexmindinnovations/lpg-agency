import 'package:api_client/api_client.dart';
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
            child: ListView.separated(
              // Bottom padding clears the floating "New order" button.
              padding: LpgSpacing.page.copyWith(
                bottom: LpgSizes.touchTarget * 2,
              ),
              itemCount: orders.length,
              separatorBuilder: (context, index) =>
                  const SizedBox(height: LpgSpacing.smd),
              itemBuilder: (context, index) => LpgFadeSlideIn(
                index: index,
                child: _OrderCard(order: orders[index]),
              ),
            ),
          );
        },
      ),
    );
  }
}

class _OrderCard extends StatelessWidget {
  const _OrderCard({required this.order});

  final OrderResponse order;

  @override
  Widget build(BuildContext context) {
    final text = context.lpgText;
    return LpgCard(
      onTap: () => context.push('/orders/${order.id}'),
      padding: const EdgeInsets.all(LpgSpacing.md),
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
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(order.reference, style: text.titleSmall),
                    const SizedBox(height: LpgSpacing.xs / 2),
                    Text(
                      LpgFormat.dateTime(order.requestedDate),
                      style: text.bodySmall,
                    ),
                  ],
                ),
              ),
              LpgStatusBadge(
                label: order.statusLabel,
                severity: order.statusSeverity,
              ),
            ],
          ),
          const SizedBox(height: LpgSpacing.md),
          const Divider(),
          const SizedBox(height: LpgSpacing.smd),
          Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Amount', style: text.labelMedium),
                    const SizedBox(height: LpgSpacing.xs / 2),
                    Text(
                      order.totalAmount != null
                          ? LpgFormat.currency(order.totalAmount!)
                          : 'Pending',
                      style: text.titleMedium,
                    ),
                  ],
                ),
              ),
              if (order.isTrackable)
                LpgButton(
                  label: 'Track',
                  onPressed: () => context.push('/orders/${order.id}/track'),
                  icon: LpgIcons.navigate,
                )
              else
                LpgButton(
                  label: 'Details',
                  onPressed: () => context.push('/orders/${order.id}'),
                  variant: LpgButtonVariant.text,
                  trailingIcon: LpgIcons.chevronRight,
                ),
            ],
          ),
        ],
      ),
    );
  }
}
