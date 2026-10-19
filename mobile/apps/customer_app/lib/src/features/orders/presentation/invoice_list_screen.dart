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
            child: ListView.separated(
              padding: LpgSpacing.page,
              itemCount: invoices.length,
              separatorBuilder: (context, index) =>
                  const SizedBox(height: LpgSpacing.smd),
              itemBuilder: (context, index) {
                final invoice = invoices[index];
                return LpgFadeSlideIn(
                  index: index,
                  child: LpgCard(
                    onTap: () =>
                        context.push('/orders/invoices/${invoice.invoiceId}'),
                    padding: const EdgeInsets.all(LpgSpacing.md),
                    child: Row(
                      children: [
                        LpgIconBox(
                          icon: LpgIcons.invoice,
                          tone: invoice.statusSeverity.tone,
                        ),
                        const SizedBox(width: LpgSpacing.smd),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(invoice.reference, style: text.titleSmall),
                              const SizedBox(height: LpgSpacing.xs / 2),
                              Text(
                                LpgFormat.date(invoice.issuedAt),
                                style: text.bodySmall,
                              ),
                              const SizedBox(height: LpgSpacing.sm),
                              LpgStatusBadge(
                                label: invoice.statusLabel,
                                severity: invoice.statusSeverity,
                              ),
                            ],
                          ),
                        ),
                        const SizedBox(width: LpgSpacing.sm),
                        Column(
                          crossAxisAlignment: CrossAxisAlignment.end,
                          children: [
                            Text(
                              LpgFormat.currency(invoice.totalAmount),
                              style: text.titleMedium,
                            ),
                            const SizedBox(height: LpgSpacing.xs),
                            Text('View', style: text.labelMedium),
                          ],
                        ),
                      ],
                    ),
                  ),
                );
              },
            ),
          );
        },
      ),
    );
  }
}
