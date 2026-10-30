import 'dart:async';

import 'package:api_client/api_client.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../api_result.dart';
import '../data/customers_provider.dart';

/// Status badge for a customer that is not in good standing; an active
/// customer needs no badge.
LpgStatusSeverity customerStatusSeverity(String status) => switch (status) {
  'active' => LpgStatusSeverity.success,
  'suspended' || 'closed' || 'blocked' => LpgStatusSeverity.danger,
  _ => LpgStatusSeverity.warning,
};

/// Every customer of the agency with a search box. Tapping a row opens the
/// customer.
class CustomersScreen extends ConsumerStatefulWidget {
  const CustomersScreen({super.key});

  @override
  ConsumerState<CustomersScreen> createState() => _CustomersScreenState();
}

class _CustomersScreenState extends ConsumerState<CustomersScreen> {
  final _controller = TextEditingController();
  Timer? _debounce;
  String _search = '';
  int _pages = 1;

  @override
  void dispose() {
    _debounce?.cancel();
    _controller.dispose();
    super.dispose();
  }

  void _onChanged(String value) {
    _debounce?.cancel();
    _debounce = Timer(const Duration(milliseconds: 350), () {
      if (!mounted) return;
      setState(() {
        _search = value.trim();
        _pages = 1;
      });
    });
  }

  void _refresh() => ref.invalidate(customersProvider);

  Future<void> _add() async {
    final created = await context.pushNamed<CustomerResponse>('customer_new');
    if (created == null || !mounted) return;
    _refresh();
    context.pushNamed(
      'customer_detail',
      pathParameters: {'customerId': created.id},
    );
  }

  @override
  Widget build(BuildContext context) {
    final pages = [
      for (var p = 1; p <= _pages; p++)
        ref.watch(customersProvider((_search, p))),
    ];
    final first = pages.first;
    final last = pages.last;
    final customers = [for (final page in pages) ...?page.value?.items];
    final total = first.value?.total ?? 0;
    final hasMore =
        !last.isLoading && !last.hasError && customers.length < total;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Customers'),
        actions: [
          IconButton(
            tooltip: 'Add customer',
            icon: const Icon(LpgIcons.add),
            onPressed: _add,
          ),
          IconButton(
            tooltip: 'Refresh',
            icon: const Icon(LpgIcons.sync),
            onPressed: _refresh,
          ),
        ],
      ),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(
              LpgSpacing.md,
              LpgSpacing.sm,
              LpgSpacing.md,
              LpgSpacing.sm,
            ),
            child: LpgTextField(
              label: 'Search customers',
              hintText: 'Name, phone or consumer number',
              controller: _controller,
              prefixIcon: LpgIcons.search,
              onChanged: _onChanged,
            ),
          ),
          Expanded(
            child: first.when(
              loading: () => const Padding(
                padding: LpgSpacing.page,
                child: LpgSkeletonList(itemCount: 6),
              ),
              error: (err, _) =>
                  LpgErrorState(message: errorMessage(err), onRetry: _refresh),
              data: (_) {
                if (customers.isEmpty) {
                  return LpgEmptyState(
                    icon: LpgIcons.customers,
                    message: _search.isEmpty
                        ? 'No customers yet.'
                        : 'No customers match "$_search".',
                  );
                }
                return RefreshIndicator(
                  onRefresh: () async {
                    _refresh();
                    await ref.read(customersProvider((_search, 1)).future);
                  },
                  child: ListView(
                    physics: const AlwaysScrollableScrollPhysics(),
                    padding: LpgSpacing.page,
                    children: [
                      Padding(
                        padding: const EdgeInsets.only(bottom: LpgSpacing.sm),
                        child: Text(
                          '$total ${total == 1 ? 'customer' : 'customers'}',
                          style: context.lpgText.bodySmall?.copyWith(
                            color: context.lpgColors.textSecondary,
                          ),
                        ),
                      ),
                      LpgGroupedList(
                        children: [
                          for (final c in customers) _CustomerTile(customer: c),
                        ],
                      ),
                      const SizedBox(height: LpgSpacing.md),
                      if (last.isLoading)
                        const Center(child: LpgLoadingIndicator())
                      else if (last.hasError)
                        LpgErrorState(
                          message: errorMessage(last.error!),
                          onRetry: _refresh,
                        )
                      else if (hasMore)
                        LpgButton(
                          label: 'Load more',
                          variant: LpgButtonVariant.secondary,
                          onPressed: () => setState(() => _pages++),
                        ),
                    ],
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

class _CustomerTile extends StatelessWidget {
  const _CustomerTile({required this.customer});

  final CustomerResponse customer;

  @override
  Widget build(BuildContext context) {
    return LpgListTile(
      leading: LpgAvatar(name: customer.fullName),
      title: customer.fullName,
      subtitle: [
        customer.phoneNumber,
        if (customer.consumerNumber != null) customer.consumerNumber!,
      ].join('  ·  '),
      trailing: customer.status == 'active'
          ? null
          : LpgStatusBadge(
              label: LpgFormat.statusLabel(customer.status),
              severity: customerStatusSeverity(customer.status),
            ),
      showChevron: true,
      onTap: () => context.pushNamed(
        'customer_detail',
        pathParameters: {'customerId': customer.id},
      ),
    );
  }
}
