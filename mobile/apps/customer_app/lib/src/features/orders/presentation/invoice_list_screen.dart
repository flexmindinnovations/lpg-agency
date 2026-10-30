import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../data/invoices_provider.dart';
import 'invoice_presentation.dart';

class InvoiceListScreen extends ConsumerWidget {
  const InvoiceListScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final invoicesAsync = ref.watch(invoicesProvider);
    final text = context.lpgText;

    return Scaffold(
      appBar: AppBar(title: const Text('My Invoices')),
      body: invoicesAsync.when(
        loading: () => const LpgSkeletonList(),
        error: (err, stack) => LpgErrorState(
          message: 'Failed to load invoices',
          onRetry: () => ref.refresh(invoicesProvider),
        ),
        data: (invoices) {
          if (invoices.isEmpty) {
            return const LpgEmptyState(
              message: 'No invoices found.',
              icon: LpgIcons.invoice,
            );
          }

          return RefreshIndicator(
            onRefresh: () async => ref.refresh(invoicesProvider.future),
            child: ListView(
              padding: LpgSpacing.page,
              children: [
                LpgGroupedList(
                  children: [
                    for (final invoice in invoices)
                      LpgListTile(
                        leadingIcon: LpgIcons.invoice,
                        leadingTone: invoice.statusSeverity.tone,
                        title: invoice.reference,
                        subtitle:
                            '${invoice.statusLabel}  ·  '
                            '${LpgFormat.shortDate(invoice.issuedAt)}',
                        trailing: Text(
                          LpgFormat.currency(invoice.totalAmount),
                          style: text.titleSmall,
                        ),
                        showChevron: true,
                        onTap: () => context.push(
                          '/orders/invoices/${invoice.invoiceId}',
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
  }
}
