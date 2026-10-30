import 'package:api_client/api_client.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';

/// How an invoice's status reads and colours, the same in every list.
LpgStatusSeverity invoiceStatusSeverity(String status) => switch (status) {
  'paid' => LpgStatusSeverity.success,
  'partially_paid' => LpgStatusSeverity.warning,
  'cancelled' => LpgStatusSeverity.danger,
  'issued' => LpgStatusSeverity.info,
  _ => LpgStatusSeverity.neutral,
};

/// An invoice as one row of an [LpgGroupedList]: tinted icon, the invoice
/// number, status and date (and the customer when [showCustomer]), the total
/// on the right and a chevron.
class InvoiceTile extends StatelessWidget {
  const InvoiceTile({
    super.key,
    required this.invoice,
    required this.onTap,
    this.showCustomer = false,
  });

  final InvoiceResponse invoice;
  final VoidCallback onTap;
  final bool showCustomer;

  @override
  Widget build(BuildContext context) {
    final text = context.lpgText;
    final colors = context.lpgColors;
    final severity = invoiceStatusSeverity(invoice.status);
    final due = invoice.balanceDue;

    return LpgListTile(
      leadingIcon: LpgIcons.invoice,
      leadingTone: severity.tone,
      title: invoice.invoiceNumber ?? 'Invoice',
      subtitle: [
        if (showCustomer && invoice.customerName != null) invoice.customerName!,
        LpgFormat.statusLabel(invoice.status),
        LpgFormat.shortDate(invoice.issuedAt),
      ].join('  ·  '),
      trailing: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          Text(LpgFormat.currency(invoice.totalAmount), style: text.titleSmall),
          if (due > 0 && invoice.status != 'cancelled')
            Text(
              '${LpgFormat.currency(due)} due',
              style: text.bodySmall?.copyWith(color: colors.statusWarning),
            ),
        ],
      ),
      showChevron: true,
      onTap: onTap,
    );
  }
}
