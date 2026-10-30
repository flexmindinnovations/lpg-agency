import 'dart:async';

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../api_result.dart';
import '../../../shared/order_row.dart';
import '../data/search_provider.dart';

/// One search box for orders, customers and invoices. Each kind shows a few
/// hits and a "See all" link into its own filtered list.
class SearchScreen extends ConsumerStatefulWidget {
  const SearchScreen({super.key, this.initialQuery = ''});

  final String initialQuery;

  @override
  ConsumerState<SearchScreen> createState() => _SearchScreenState();
}

class _SearchScreenState extends ConsumerState<SearchScreen> {
  late final _controller = TextEditingController(text: widget.initialQuery);
  Timer? _debounce;
  late String _query = widget.initialQuery.trim();

  @override
  void dispose() {
    _debounce?.cancel();
    _controller.dispose();
    super.dispose();
  }

  void _onChanged(String value) {
    _debounce?.cancel();
    _debounce = Timer(const Duration(milliseconds: 350), () {
      if (mounted) setState(() => _query = value.trim());
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        titleSpacing: 0,
        title: TextField(
          controller: _controller,
          autofocus: true,
          textInputAction: TextInputAction.search,
          onChanged: _onChanged,
          onSubmitted: (v) => setState(() => _query = v.trim()),
          decoration: InputDecoration(
            hintText: 'Order no., customer, phone, invoice',
            border: InputBorder.none,
            enabledBorder: InputBorder.none,
            focusedBorder: InputBorder.none,
            filled: false,
            suffixIcon: _controller.text.isEmpty
                ? null
                : IconButton(
                    tooltip: 'Clear',
                    icon: const Icon(LpgIcons.close),
                    onPressed: () {
                      _controller.clear();
                      setState(() => _query = '');
                    },
                  ),
          ),
        ),
      ),
      body: _query.length < 2
          ? Padding(
              padding: LpgSpacing.page,
              child: LpgEmptyState(
                icon: LpgIcons.search,
                title: 'Search the agency',
                message:
                    'Type at least two characters: an order number, a '
                    "customer's name or phone, or an invoice number.",
              ),
            )
          : _Results(query: _query),
    );
  }
}

class _Results extends ConsumerWidget {
  const _Results({required this.query});

  final String query;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(searchResultsProvider(query));
    return async.when(
      loading: () => const Padding(
        padding: LpgSpacing.page,
        child: LpgSkeletonList(itemCount: 4),
      ),
      error: (err, _) => LpgErrorState(
        message: errorMessage(err),
        onRetry: () => ref.invalidate(searchResultsProvider(query)),
      ),
      data: (r) {
        if (r.isEmpty) {
          return Padding(
            padding: LpgSpacing.page,
            child: LpgEmptyState(
              icon: LpgIcons.search,
              title: 'No matches',
              message: 'Nothing found for "$query".',
            ),
          );
        }
        final text = context.lpgText;

        Widget heading(String title, int total, VoidCallback? onAll) => Padding(
          padding: const EdgeInsets.only(
            top: LpgSpacing.md,
            bottom: LpgSpacing.xs,
          ),
          child: Row(
            children: [
              Expanded(child: Text(title, style: text.titleSmall)),
              if (onAll != null && total > searchPreviewSize)
                TextButton(onPressed: onAll, child: Text('See all $total')),
            ],
          ),
        );

        return ListView(
          padding: LpgSpacing.page,
          children: [
            if (r.orders.isNotEmpty) ...[
              heading(
                'Orders',
                r.orderTotal,
                () => context.goNamed('orders', queryParameters: {'q': query}),
              ),
              LpgGroupedList(
                children: [
                  for (final o in r.orders)
                    OrderTile(
                      order: o,
                      onTap: () => context.goNamed(
                        'order_detail',
                        pathParameters: {'orderId': o.id},
                      ),
                    ),
                ],
              ),
            ],
            if (r.customers.isNotEmpty) ...[
              heading('Customers', r.customerTotal, null),
              for (final c in r.customers)
                Padding(
                  padding: const EdgeInsets.only(bottom: LpgSpacing.xs),
                  child: LpgListTile(
                    leadingIcon: LpgIcons.user,
                    title: c.fullName,
                    subtitle:
                        '${c.phoneNumber}'
                        '${c.consumerNumber == null ? '' : '  •  ${c.consumerNumber}'}',
                  ),
                ),
            ],
            if (r.invoices.isNotEmpty) ...[
              heading('Invoices', r.invoiceTotal, null),
              for (final i in r.invoices)
                Padding(
                  padding: const EdgeInsets.only(bottom: LpgSpacing.xs),
                  child: LpgListTile(
                    leadingIcon: LpgIcons.invoice,
                    title: i.invoiceNumber ?? 'Invoice',
                    subtitle:
                        '${LpgFormat.currency(i.totalAmount)}  •  '
                        '${LpgFormat.statusLabel(i.status)}  •  '
                        '${LpgFormat.shortDate(i.issuedAt)}',
                  ),
                ),
            ],
          ],
        );
      },
    );
  }
}
