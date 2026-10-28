// Order List Screen for Admin App
import 'dart:async';

import 'package:api_client/api_client.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../api_result.dart';
import '../data/orders_provider.dart';
import '../domain/order_flow.dart';

class OrderListScreen extends ConsumerStatefulWidget {
  const OrderListScreen({super.key});

  @override
  ConsumerState<OrderListScreen> createState() => _OrderListScreenState();
}

class _OrderListScreenState extends ConsumerState<OrderListScreen> {
  OrderFilter _selectedFilter = orderFilters.first;
  final _searchController = TextEditingController();
  Timer? _debounce;
  String _search = '';

  /// How many pages of 50 are on screen; "Load more" adds one.
  int _pages = 1;

  @override
  void dispose() {
    _debounce?.cancel();
    _searchController.dispose();
    super.dispose();
  }

  /// A filter covering one status is answered by the server; one covering
  /// several (On a trip, Delivered) filters the loaded pages here.
  OrderQuery get _query => OrderQuery(
    search: _search,
    status: _selectedFilter.statuses.length == 1
        ? _selectedFilter.statuses.first
        : null,
  );

  void _onSearchChanged(String value) {
    _debounce?.cancel();
    _debounce = Timer(const Duration(milliseconds: 350), () {
      if (!mounted) return;
      setState(() {
        _search = value.trim();
        _pages = 1;
      });
    });
  }

  void _refresh() {
    ref.invalidate(adminOrdersProvider);
  }

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;
    final text = context.lpgText;

    final query = _query;
    final pages = [
      for (var p = 1; p <= _pages; p++)
        ref.watch(adminOrdersProvider((query, p))),
    ];
    final first = pages.first;
    final last = pages.last;
    final orders = [
      for (final page in pages)
        for (final o in page.value?.items ?? const <OrderResponse>[])
          if (_selectedFilter.matches(o.status)) o,
    ];
    final total = first.value?.total ?? 0;
    final loadedCount = pages.fold<int>(
      0,
      (n, page) => n + (page.value?.items.length ?? 0),
    );
    final hasMore = !last.isLoading && !last.hasError && loadedCount < total;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Orders'),
        actions: [
          IconButton(
            tooltip: 'Refresh',
            icon: const Icon(LpgIcons.sync),
            onPressed: _refresh,
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => context.goNamed('order_new'),
        icon: const Icon(LpgIcons.add),
        label: const Text('New order'),
      ),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(
              LpgSpacing.md,
              LpgSpacing.sm,
              LpgSpacing.md,
              0,
            ),
            child: LpgTextField(
              label: 'Search orders',
              hintText: 'Order number, customer, phone',
              controller: _searchController,
              prefixIcon: LpgIcons.search,
              onChanged: _onSearchChanged,
            ),
          ),
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.symmetric(
              horizontal: LpgSpacing.md,
              vertical: LpgSpacing.sm,
            ),
            child: Row(
              children: orderFilters.map((filter) {
                final selected = _selectedFilter == filter;
                return Padding(
                  padding: const EdgeInsets.only(right: LpgSpacing.xs),
                  child: FilterChip(
                    label: Text(filter.label),
                    selected: selected,
                    onSelected: (_) => setState(() {
                      _selectedFilter = filter;
                      _pages = 1;
                    }),
                  ),
                );
              }).toList(),
            ),
          ),
          Expanded(
            child: first.when(
              loading: () => const LpgSkeletonList(itemCount: 5),
              error: (err, _) =>
                  LpgErrorState(message: errorMessage(err), onRetry: _refresh),
              data: (_) {
                if (orders.isEmpty && !hasMore) {
                  return LpgEmptyState(
                    message: _search.isEmpty
                        ? 'No orders match the selected filter.'
                        : 'No orders match "$_search".',
                    icon: LpgIcons.orders,
                  );
                }

                return RefreshIndicator(
                  onRefresh: () async {
                    _refresh();
                    await ref.read(adminOrdersProvider((query, 1)).future);
                  },
                  child: ListView.separated(
                    physics: const AlwaysScrollableScrollPhysics(),
                    padding: LpgSpacing.page,
                    itemCount: orders.length + 1,
                    separatorBuilder: (_, _) =>
                        const SizedBox(height: LpgSpacing.sm),
                    itemBuilder: (context, index) {
                      if (index == orders.length) {
                        return _ListFooter(
                          loading: last.isLoading,
                          error: last.hasError
                              ? errorMessage(last.error!)
                              : null,
                          hasMore: hasMore,
                          onMore: () => setState(() => _pages++),
                          onRetry: _refresh,
                        );
                      }
                      final order = orders[index];
                      return LpgCard(
                        onTap: () => context.goNamed(
                          'order_detail',
                          pathParameters: {'orderId': order.id},
                        ),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              mainAxisAlignment: MainAxisAlignment.spaceBetween,
                              children: [
                                Text(
                                  LpgFormat.orderNumber(
                                    order.orderNumber,
                                    order.id,
                                  ),
                                  style: text.titleMedium,
                                ),
                                LpgStatusBadge(
                                  label: LpgFormat.statusLabel(order.status),
                                  severity: orderStatusSeverity(order.status),
                                ),
                              ],
                            ),
                            const SizedBox(height: LpgSpacing.xs),
                            Text(
                              order.customerName ?? 'Customer',
                              style: text.bodyMedium?.copyWith(
                                color: colors.textSecondary,
                              ),
                            ),
                            const SizedBox(height: LpgSpacing.xs),
                            Row(
                              mainAxisAlignment: MainAxisAlignment.spaceBetween,
                              children: [
                                Text(
                                  LpgFormat.date(order.requestedDate),
                                  style: text.bodySmall?.copyWith(
                                    color: colors.textSecondary,
                                  ),
                                ),
                                Text(
                                  LpgFormat.currency(order.totalAmount ?? 0.0),
                                  style: text.titleSmall?.copyWith(
                                    color: colors.actionPrimary,
                                  ),
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
          ),
        ],
      ),
    );
  }
}

/// The end of the list: a spinner while the next page loads, a retry after a
/// failure, "Load more" while the server has more, else nothing.
class _ListFooter extends StatelessWidget {
  const _ListFooter({
    required this.loading,
    required this.hasMore,
    required this.onMore,
    required this.onRetry,
    this.error,
  });

  final bool loading;
  final bool hasMore;
  final String? error;
  final VoidCallback onMore;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    if (loading) {
      return const Padding(
        padding: EdgeInsets.all(LpgSpacing.md),
        child: Center(child: LpgLoadingIndicator()),
      );
    }
    if (error != null) {
      return LpgErrorState(message: error!, onRetry: onRetry);
    }
    if (hasMore) {
      return LpgButton(
        label: 'Load more',
        variant: LpgButtonVariant.secondary,
        onPressed: onMore,
      );
    }
    return const SizedBox(height: LpgSpacing.xxl * 2);
  }
}
