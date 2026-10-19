import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../payments/presentation/pay_online_section.dart';
import '../data/cylinder_types_provider.dart';
import '../data/invoices_provider.dart';
import 'invoice_presentation.dart';

class InvoiceDetailScreen extends ConsumerWidget {
  const InvoiceDetailScreen({super.key, required this.invoiceId});

  final String invoiceId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final invoiceAsync = ref.watch(invoiceDetailProvider(invoiceId));
    final colors = context.lpgColors;
    final text = context.lpgText;

    return Scaffold(
      appBar: AppBar(title: const Text('Invoice Details')),
      body: invoiceAsync.when(
        loading: () => const LpgSkeletonList(itemCount: 4),
        error: (err, _) => LpgErrorState(
          message: 'Failed to load this invoice\n$err',
          onRetry: () => ref.refresh(invoiceDetailProvider(invoiceId)),
        ),
        data: (invoice) {
          if (invoice == null) {
            return const LpgEmptyState(
              message: 'This invoice could not be found.',
              icon: LpgIcons.invoice,
            );
          }

          final cylinderTypesAsync = ref.watch(cylinderTypesProvider);
          final cylinderNames = cylinderTypesAsync.maybeWhen(
            data: (types) => {for (final t in types) t.id: t.name},
            orElse: () => const <String, String>{},
          );
          final balanceDue = invoice.balanceDue;

          final sections = <Widget>[
            LpgHeroCard(
              watermark: LpgIcons.invoice,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: Text(
                          invoice.reference,
                          style: text.titleMedium?.copyWith(
                            color: colors.onHero,
                          ),
                        ),
                      ),
                      LpgStatusBadge(
                        label: invoice.statusLabel,
                        severity: invoice.statusSeverity,
                      ),
                    ],
                  ),
                  const SizedBox(height: LpgSpacing.lg),
                  Text(
                    'Total',
                    style: text.labelLarge?.copyWith(
                      color: colors.onHero.withValues(alpha: 0.8),
                    ),
                  ),
                  Text(
                    LpgFormat.currency(invoice.totalAmount),
                    style: text.displayMedium?.copyWith(color: colors.onHero),
                  ),
                  const SizedBox(height: LpgSpacing.smd),
                  Text(
                    [
                      'Issued ${LpgFormat.date(invoice.issuedAt)}',
                      if (invoice.orderNumber != null)
                        'Order #${invoice.orderNumber}',
                    ].join('  ·  '),
                    style: text.bodySmall?.copyWith(
                      color: colors.onHero.withValues(alpha: 0.8),
                    ),
                  ),
                ],
              ),
            ),
            const LpgSectionHeader(title: 'Cylinders'),
            LpgCard(
              padding: const EdgeInsets.symmetric(vertical: LpgSpacing.xs),
              child: Column(
                children: [
                  for (final (index, line) in invoice.lines.indexed) ...[
                    if (index > 0) const Divider(indent: LpgSpacing.md),
                    LpgListTile(
                      leadingIcon: LpgIcons.cylinder,
                      title: cylinderNames[line.cylinderTypeId] ?? 'Cylinder',
                      subtitle:
                          'Qty ${line.quantity} × '
                          '${LpgFormat.currency(line.unitPrice)}',
                      trailing: Text(
                        LpgFormat.currency(line.totalAmount),
                        style: text.titleSmall,
                      ),
                    ),
                  ],
                ],
              ),
            ),
            const LpgSectionHeader(title: 'Summary'),
            LpgCard(
              child: Column(
                children: [
                  LpgKeyValueRow(
                    label: 'Subtotal',
                    value: LpgFormat.currency(invoice.subtotal),
                  ),
                  LpgKeyValueRow(
                    label: 'Tax',
                    value: LpgFormat.currency(invoice.taxAmount),
                  ),
                  const Padding(
                    padding: EdgeInsets.symmetric(vertical: LpgSpacing.sm),
                    child: Divider(),
                  ),
                  LpgKeyValueRow(
                    label: 'Total',
                    value: LpgFormat.currency(invoice.totalAmount),
                    emphasize: true,
                  ),
                  LpgKeyValueRow(
                    label: 'Amount Paid',
                    value: LpgFormat.currency(invoice.amountPaid),
                    valueColor: colors.statusSuccess,
                  ),
                  LpgKeyValueRow(
                    label: 'Balance Due',
                    value: LpgFormat.currency(balanceDue),
                    valueColor: balanceDue > 0 ? colors.statusDanger : null,
                  ),
                ],
              ),
            ),
            if (invoice.payments.isNotEmpty) ...[
              const LpgSectionHeader(title: 'Payment History'),
              LpgCard(
                padding: const EdgeInsets.symmetric(vertical: LpgSpacing.xs),
                child: Column(
                  children: [
                    for (final (index, payment)
                        in invoice.payments.indexed) ...[
                      if (index > 0) const Divider(indent: LpgSpacing.md),
                      LpgListTile(
                        leadingIcon: LpgIcons.cash,
                        leadingTone: LpgTone.success,
                        title: LpgFormat.statusLabel(payment.method),
                        subtitle: LpgFormat.dateTime(payment.collectedAt),
                        trailing: Text(
                          LpgFormat.currency(payment.amount),
                          style: text.titleSmall?.copyWith(
                            color: colors.statusSuccess,
                          ),
                        ),
                      ),
                    ],
                  ],
                ),
              ),
            ],
            const SizedBox(height: LpgSpacing.lg),
            PayOnlineSection(
              orderId: invoice.orderId,
              canPay:
                  balanceDue > 0 &&
                  (invoice.status == 'issued' ||
                      invoice.status == 'partially_paid'),
              onPaid: () {
                ref.invalidate(invoiceDetailProvider(invoiceId));
                ref.invalidate(invoicesProvider);
              },
            ),
          ];

          return RefreshIndicator(
            onRefresh: () {
              ref.invalidate(invoicesProvider);
              return ref.refresh(invoiceDetailProvider(invoiceId).future);
            },
            child: ListView(
              physics: const AlwaysScrollableScrollPhysics(),
              padding: LpgSpacing.page,
              children: [
                for (var i = 0; i < sections.length; i++)
                  LpgFadeSlideIn(index: i, child: sections[i]),
              ],
            ),
          );
        },
      ),
    );
  }
}
