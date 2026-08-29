import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import '../data/invoices_provider.dart';

class InvoiceListScreen extends ConsumerWidget {
  const InvoiceListScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final invoicesAsync = ref.watch(invoicesProvider);
    final colors = Theme.of(context).extension<LpgColors>()!;
    final theme = Theme.of(context);

    return Scaffold(
      backgroundColor: theme.scaffoldBackgroundColor,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        centerTitle: true,
        title: Text(
          'My Invoices',
          style: theme.textTheme.titleMedium?.copyWith(
            fontWeight: FontWeight.w600,
            color: colors.textPrimary,
          ),
        ),
      ),
      body: invoicesAsync.when(
        loading: () => const Center(child: LpgLoadingIndicator()),
        error: (err, stack) => LpgEmptyState(
          message: 'Failed to load invoices',
          icon: Icons.error_outline,
          actionLabel: 'Retry',
          onAction: () => ref.refresh(invoicesProvider),
        ),
        data: (invoices) {
          if (invoices.isEmpty) {
            return const LpgEmptyState(
              message: 'No invoices found.',
              icon: Icons.receipt_outlined,
            );
          }

          return RefreshIndicator(
            onRefresh: () async => ref.refresh(invoicesProvider.future),
            child: ListView.separated(
              padding: const EdgeInsets.all(16),
              itemCount: invoices.length,
              separatorBuilder: (context, index) => const SizedBox(height: 12),
              itemBuilder: (context, index) {
                final invoice = invoices[index];
                final isPaid = invoice.status == 'paid';

                return LpgCard(
                  onTap: () =>
                      context.push('/orders/invoices/${invoice.invoiceId}'),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Text(
                            'INV-${invoice.invoiceNumber ?? invoice.invoiceId.substring(0, 8).toUpperCase()}',
                            style: theme.textTheme.titleSmall?.copyWith(
                              fontWeight: FontWeight.bold,
                              color: colors.textPrimary,
                            ),
                          ),
                          LpgStatusBadge(
                            label: invoice.status.toUpperCase(),
                            severity: isPaid
                                ? LpgStatusSeverity.success
                                : LpgStatusSeverity.warning,
                          ),
                        ],
                      ),
                      const SizedBox(height: 12),
                      Row(
                        children: [
                          Icon(
                            Icons.calendar_today_outlined,
                            size: 14,
                            color: colors.textSecondary,
                          ),
                          const SizedBox(width: 8),
                          Text(
                            DateFormat('MMM dd, yyyy').format(invoice.issuedAt),
                            style: theme.textTheme.bodySmall?.copyWith(
                              color: colors.textSecondary,
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 16),
                      Divider(height: 1, color: colors.borderDefault),
                      const SizedBox(height: 16),
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                'Amount',
                                style: theme.textTheme.labelSmall?.copyWith(
                                  color: colors.textSecondary,
                                ),
                              ),
                              Text(
                                '₹${invoice.totalAmount.toStringAsFixed(2)}',
                                style: theme.textTheme.titleMedium?.copyWith(
                                  fontWeight: FontWeight.bold,
                                  color: colors.textPrimary,
                                ),
                              ),
                            ],
                          ),
                          LpgButton(
                            label: 'View',
                            onPressed: () => context.push(
                              '/orders/invoices/${invoice.invoiceId}',
                            ),
                            variant: LpgButtonVariant.text,
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
    );
  }
}
