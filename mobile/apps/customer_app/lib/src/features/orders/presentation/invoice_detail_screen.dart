import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../data/cylinder_types_provider.dart';
import '../data/invoices_provider.dart';

LpgStatusSeverity _statusSeverity(String status) => switch (status) {
  'paid' => LpgStatusSeverity.success,
  'partially_paid' => LpgStatusSeverity.warning,
  'issued' => LpgStatusSeverity.info,
  'cancelled' || 'refunded' => LpgStatusSeverity.danger,
  _ => LpgStatusSeverity.neutral,
};

class InvoiceDetailScreen extends ConsumerWidget {
  const InvoiceDetailScreen({super.key, required this.invoiceId});

  final String invoiceId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final invoiceAsync = ref.watch(invoiceDetailProvider(invoiceId));
    final colors = Theme.of(context).extension<LpgColors>()!;
    final theme = Theme.of(context);

    return Scaffold(
      backgroundColor: theme.scaffoldBackgroundColor,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        centerTitle: true,
        title: Text(
          'Invoice Details',
          style: theme.textTheme.titleMedium?.copyWith(
            fontWeight: FontWeight.w600,
            color: colors.textPrimary,
          ),
        ),
      ),
      body: invoiceAsync.when(
        loading: () => const Center(child: LpgLoadingIndicator()),
        error: (err, _) => LpgEmptyState(
          message: 'Failed to load this invoice\n$err',
          icon: Icons.error_outline,
          actionLabel: 'Retry',
          onAction: () => ref.refresh(invoiceDetailProvider(invoiceId)),
        ),
        data: (invoice) {
          if (invoice == null) {
            return const LpgEmptyState(
              message: 'This invoice could not be found.',
              icon: Icons.receipt_outlined,
            );
          }

          final cylinderTypesAsync = ref.watch(cylinderTypesProvider);
          final cylinderNames = cylinderTypesAsync.maybeWhen(
            data: (types) => {for (final t in types) t.id: t.name},
            orElse: () => const <String, String>{},
          );
          final balanceDue = invoice.totalAmount - invoice.amountPaid;

          return ListView(
            padding: const EdgeInsets.all(24.0),
            children: [
              LpgCard(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Expanded(
                          child: Text(
                            'INV-${invoice.invoiceNumber ?? invoice.invoiceId.substring(0, 8).toUpperCase()}',
                            style: theme.textTheme.titleLarge?.copyWith(
                              fontWeight: FontWeight.bold,
                              color: colors.textPrimary,
                            ),
                          ),
                        ),
                        LpgStatusBadge(
                          label: invoice.status
                              .replaceAll('_', ' ')
                              .toUpperCase(),
                          severity: _statusSeverity(invoice.status),
                        ),
                      ],
                    ),
                    const SizedBox(height: 16),
                    Row(
                      children: [
                        Icon(
                          Icons.calendar_today_outlined,
                          size: 16,
                          color: colors.textSecondary,
                        ),
                        const SizedBox(width: 6),
                        Text(
                          DateFormat('MMM dd, yyyy').format(invoice.issuedAt),
                          style: theme.textTheme.bodySmall?.copyWith(
                            color: colors.textSecondary,
                          ),
                        ),
                        if (invoice.orderNumber != null) ...[
                          const SizedBox(width: 16),
                          Icon(
                            Icons.receipt_long_outlined,
                            size: 16,
                            color: colors.textSecondary,
                          ),
                          const SizedBox(width: 6),
                          Text(
                            'Order #${invoice.orderNumber}',
                            style: theme.textTheme.bodySmall?.copyWith(
                              color: colors.textSecondary,
                            ),
                          ),
                        ],
                      ],
                    ),
                  ],
                ),
              ),

              const SizedBox(height: 24),
              Text(
                'Cylinders',
                style: theme.textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.w600,
                  color: colors.textPrimary,
                ),
              ),
              const SizedBox(height: 12),
              LpgCard(
                padding: EdgeInsets.zero,
                child: Column(
                  children: [
                    for (final (index, line) in invoice.lines.indexed) ...[
                      if (index > 0)
                        Divider(
                          height: 1,
                          indent: 16,
                          endIndent: 16,
                          color: colors.borderDefault,
                        ),
                      LpgListTile(
                        leadingIcon: Icons.local_gas_station_outlined,
                        title: cylinderNames[line.cylinderTypeId] ?? 'Cylinder',
                        subtitle:
                            'Qty ${line.quantity} × ₹${line.unitPrice.toStringAsFixed(2)}',
                        trailing: Text(
                          '₹${line.totalAmount.toStringAsFixed(2)}',
                          style: theme.textTheme.titleSmall?.copyWith(
                            fontWeight: FontWeight.w600,
                            color: colors.textPrimary,
                          ),
                        ),
                      ),
                    ],
                  ],
                ),
              ),

              const SizedBox(height: 24),
              Text(
                'Summary',
                style: theme.textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.w600,
                  color: colors.textPrimary,
                ),
              ),
              const SizedBox(height: 12),
              LpgCard(
                child: Column(
                  children: [
                    _SummaryRow(
                      label: 'Subtotal',
                      value: invoice.subtotal,
                      theme: theme,
                      colors: colors,
                    ),
                    const SizedBox(height: 8),
                    _SummaryRow(
                      label: 'Tax',
                      value: invoice.taxAmount,
                      theme: theme,
                      colors: colors,
                    ),
                    const SizedBox(height: 12),
                    Divider(height: 1, color: colors.borderDefault),
                    const SizedBox(height: 12),
                    _SummaryRow(
                      label: 'Total',
                      value: invoice.totalAmount,
                      theme: theme,
                      colors: colors,
                      emphasize: true,
                    ),
                    const SizedBox(height: 8),
                    _SummaryRow(
                      label: 'Amount Paid',
                      value: invoice.amountPaid,
                      theme: theme,
                      colors: colors,
                    ),
                    const SizedBox(height: 8),
                    _SummaryRow(
                      label: 'Balance Due',
                      value: balanceDue,
                      theme: theme,
                      colors: colors,
                      valueColor: balanceDue > 0 ? colors.statusDanger : null,
                    ),
                  ],
                ),
              ),

              if (invoice.payments.isNotEmpty) ...[
                const SizedBox(height: 24),
                Text(
                  'Payment History',
                  style: theme.textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.w600,
                    color: colors.textPrimary,
                  ),
                ),
                const SizedBox(height: 12),
                LpgCard(
                  padding: EdgeInsets.zero,
                  child: Column(
                    children: [
                      for (final (index, payment)
                          in invoice.payments.indexed) ...[
                        if (index > 0)
                          Divider(
                            height: 1,
                            indent: 16,
                            endIndent: 16,
                            color: colors.borderDefault,
                          ),
                        LpgListTile(
                          leadingIcon: Icons.payments_outlined,
                          title: payment.method
                              .replaceAll('_', ' ')
                              .toUpperCase(),
                          subtitle: DateFormat(
                            'MMM dd, yyyy • hh:mm a',
                          ).format(payment.collectedAt),
                          trailing: Text(
                            '₹${payment.amount.toStringAsFixed(2)}',
                            style: theme.textTheme.titleSmall?.copyWith(
                              fontWeight: FontWeight.w600,
                              color: colors.statusSuccess,
                            ),
                          ),
                        ),
                      ],
                    ],
                  ),
                ),
              ],
              const SizedBox(height: 24),
            ],
          );
        },
      ),
    );
  }
}

class _SummaryRow extends StatelessWidget {
  const _SummaryRow({
    required this.label,
    required this.value,
    required this.theme,
    required this.colors,
    this.emphasize = false,
    this.valueColor,
  });

  final String label;
  final double value;
  final ThemeData theme;
  final LpgColors colors;
  final bool emphasize;
  final Color? valueColor;

  @override
  Widget build(BuildContext context) {
    final style = emphasize
        ? theme.textTheme.titleMedium?.copyWith(
            fontWeight: FontWeight.bold,
            color: valueColor ?? colors.textPrimary,
          )
        : theme.textTheme.bodyMedium?.copyWith(
            color: valueColor ?? colors.textPrimary,
          );

    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(
          label,
          style: theme.textTheme.bodyMedium?.copyWith(
            color: colors.textSecondary,
          ),
        ),
        Text('₹${value.toStringAsFixed(2)}', style: style),
      ],
    );
  }
}
