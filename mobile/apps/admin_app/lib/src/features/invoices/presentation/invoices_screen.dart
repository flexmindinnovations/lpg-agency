import 'dart:async';

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../api_result.dart';
import '../../../shared/invoice_tile.dart';
import '../../customers/data/customers_provider.dart';
import '../data/invoices_provider.dart';

/// The status chips: label and the server's status value (`null` = all).
const _statusFilters = <(String, String?)>[
  ('All', null),
  ('Issued', 'issued'),
  ('Part paid', 'partially_paid'),
  ('Paid', 'paid'),
  ('Cancelled', 'cancelled'),
];

/// The agency's invoices: search by number, order or customer, narrow by
/// status, and optionally by one customer (when opened from their page).
class InvoicesScreen extends ConsumerStatefulWidget {
  const InvoicesScreen({super.key, this.customerId, this.initialStatus});

  final String? customerId;
  final String? initialStatus;

  @override
  ConsumerState<InvoicesScreen> createState() => _InvoicesScreenState();
}

class _InvoicesScreenState extends ConsumerState<InvoicesScreen> {
  final _controller = TextEditingController();
  Timer? _debounce;
  String _search = '';
  late String? _status = widget.initialStatus;
  int _pages = 1;

  @override
  void dispose() {
    _debounce?.cancel();
    _controller.dispose();
    super.dispose();
  }

  InvoiceQuery get _query => InvoiceQuery(
    search: _search,
    status: _status,
    customerId: widget.customerId,
  );

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

  void _refresh() => ref.invalidate(invoicesProvider);

  @override
  Widget build(BuildContext context) {
    final query = _query;
    final pages = [
      for (var p = 1; p <= _pages; p++) ref.watch(invoicesProvider((query, p))),
    ];
    final first = pages.first;
    final last = pages.last;
    final invoices = [for (final page in pages) ...?page.value?.items];
    final total = first.value?.total ?? 0;
    final hasMore =
        !last.isLoading && !last.hasError && invoices.length < total;
    final customerName = widget.customerId == null
        ? null
        : ref.watch(customerDetailProvider(widget.customerId!)).value?.fullName;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Invoices'),
        actions: [
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
              0,
            ),
            child: LpgTextField(
              label: 'Search invoices',
              hintText: 'Invoice, order or customer',
              controller: _controller,
              prefixIcon: LpgIcons.search,
              onChanged: _onChanged,
            ),
          ),
          if (widget.customerId != null)
            Padding(
              padding: const EdgeInsets.fromLTRB(
                LpgSpacing.md,
                LpgSpacing.sm,
                LpgSpacing.md,
                0,
              ),
              child: Align(
                alignment: Alignment.centerLeft,
                child: InputChip(
                  avatar: const Icon(LpgIcons.user, size: LpgSizes.iconSm),
                  label: Text(customerName ?? 'This customer'),
                  onDeleted: () => context.go('/invoices'),
                  deleteButtonTooltipMessage: 'Show every customer',
                ),
              ),
            ),
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.symmetric(
              horizontal: LpgSpacing.md,
              vertical: LpgSpacing.sm,
            ),
            child: Row(
              children: [
                for (final (label, value) in _statusFilters)
                  Padding(
                    padding: const EdgeInsets.only(right: LpgSpacing.xs),
                    child: FilterChip(
                      label: Text(label),
                      selected: _status == value,
                      onSelected: (_) => setState(() {
                        _status = value;
                        _pages = 1;
                      }),
                    ),
                  ),
              ],
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
                if (invoices.isEmpty) {
                  return LpgEmptyState(
                    icon: LpgIcons.invoice,
                    message: _search.isEmpty && _status == null
                        ? 'No invoices yet.'
                        : 'No invoices match.',
                  );
                }
                return RefreshIndicator(
                  onRefresh: () async {
                    _refresh();
                    await ref.read(invoicesProvider((query, 1)).future);
                  },
                  child: ListView(
                    physics: const AlwaysScrollableScrollPhysics(),
                    padding: LpgSpacing.page,
                    children: [
                      LpgGroupedList(
                        children: [
                          for (final i in invoices)
                            InvoiceTile(
                              invoice: i,
                              showCustomer: widget.customerId == null,
                              onTap: () => context.pushNamed(
                                'invoice_detail',
                                pathParameters: {'invoiceId': i.invoiceId},
                              ),
                            ),
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
