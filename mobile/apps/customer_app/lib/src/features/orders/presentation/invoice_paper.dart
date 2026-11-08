import 'package:api_client/api_client.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';

import '../../../i18n/customer_strings.dart';
import 'invoice_presentation.dart';

/// The invoice drawn like a sheet of paper: white, hairline-bordered, narrow
/// and centred, with a ruled item table and a totals block. Every colour comes
/// from the active theme, so it follows light, dark and high-contrast.
class InvoicePaper extends StatelessWidget {
  const InvoicePaper({
    super.key,
    required this.invoice,
    required this.cylinderNames,
  });

  final InvoiceResponse invoice;
  final Map<String, String> cylinderNames;

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;
    final strings = context.strings;
    final base = Theme.of(context).textTheme;
    final ink = colors.textPrimary;
    final rule = colors.rowDivider;
    final small = base.bodySmall?.copyWith(color: colors.textSecondary);
    final body = base.bodyMedium?.copyWith(color: ink);
    final bold = base.bodyMedium?.copyWith(
      color: ink,
      fontWeight: FontWeight.w700,
    );
    final balanceDue = invoice.balanceDue;

    Widget kv(String l, String v, {TextStyle? style, Color? color}) => Padding(
      padding: const EdgeInsets.symmetric(vertical: 3),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(l, style: style ?? body),
          Text(v, style: (style ?? body)?.copyWith(color: color)),
        ],
      ),
    );

    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 520),
        child: Container(
          padding: const EdgeInsets.all(LpgSpacing.lg),
          decoration: BoxDecoration(
            color: colors.sheet,
            borderRadius: BorderRadius.circular(LpgRadius.md),
            border: Border.all(color: colors.outline),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'INVOICE',
                          style: base.headlineSmall?.copyWith(
                            color: ink,
                            fontWeight: FontWeight.w800,
                            letterSpacing: 1,
                          ),
                        ),
                        Text(invoice.reference, style: small),
                      ],
                    ),
                  ),
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.end,
                    children: [
                      Text(
                        strings.invoice.issued(
                          date: LpgFormat.date(invoice.issuedAt),
                        ),
                        style: small,
                      ),
                      const SizedBox(height: 4),
                      LpgStatusBadge(
                        label: invoice.statusLabel,
                        severity: invoice.statusSeverity,
                      ),
                    ],
                  ),
                ],
              ),
              const SizedBox(height: LpgSpacing.md),
              if (invoice.customerName != null || invoice.orderNumber != null)
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    if (invoice.customerName != null)
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(strings.invoice.billedTo, style: small),
                            Text(invoice.customerName!, style: bold),
                            if (invoice.customerGstin != null)
                              Text(
                                strings.invoice.gstin(
                                  gstin: invoice.customerGstin!,
                                ),
                                style: small,
                              ),
                          ],
                        ),
                      ),
                    if (invoice.orderNumber != null)
                      Column(
                        crossAxisAlignment: CrossAxisAlignment.end,
                        children: [
                          Text(strings.invoice.order, style: small),
                          Text(invoice.orderNumber!, style: bold),
                        ],
                      ),
                  ],
                ),
              const SizedBox(height: LpgSpacing.md),
              Divider(color: rule, height: 1),
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 6),
                child: Row(
                  children: [
                    Expanded(child: Text(strings.invoice.item, style: small)),
                    Text(strings.invoice.amount, style: small),
                  ],
                ),
              ),
              Divider(color: rule, height: 1),
              for (final line in invoice.lines)
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 8),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              cylinderNames[line.cylinderTypeId] ?? 'Cylinder',
                              style: bold,
                            ),
                            Text(
                              [
                                '${line.quantity} × '
                                    '${LpgFormat.currency(line.unitPrice)}',
                                if (line.taxAmount > 0)
                                  'GST ${LpgFormat.currency(line.taxAmount)}',
                              ].join('  ·  '),
                              style: small,
                            ),
                          ],
                        ),
                      ),
                      Text(LpgFormat.currency(line.totalAmount), style: body),
                    ],
                  ),
                ),
              Divider(color: rule, height: 1),
              const SizedBox(height: LpgSpacing.sm),
              kv('Subtotal', LpgFormat.currency(invoice.subtotal)),
              kv('GST', LpgFormat.currency(invoice.taxAmount)),
              kv('Total', LpgFormat.currency(invoice.totalAmount), style: bold),
              kv(
                'Amount paid',
                LpgFormat.currency(invoice.amountPaid),
                color: colors.statusSuccess,
              ),
              kv(
                'Balance due',
                LpgFormat.currency(balanceDue),
                style: bold,
                color: balanceDue > 0 ? colors.statusDanger : null,
              ),
              if (invoice.payments.isNotEmpty) ...[
                const SizedBox(height: LpgSpacing.md),
                Text(strings.invoice.payments, style: small),
                for (final p in invoice.payments)
                  kv(
                    '${LpgFormat.statusLabel(p.method)}  ·  '
                    '${LpgFormat.shortDate(p.collectedAt)}',
                    LpgFormat.currency(p.amount),
                  ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
