import 'package:api_client/api_client.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../api_result.dart';
import '../data/invoices_provider.dart';

/// The agency's UPI QR for what is still owed on an invoice, to hold up to
/// the customer. Explains what to do when the agency has no UPI ID yet.
class UpiQrSheet extends ConsumerWidget {
  const UpiQrSheet({super.key, required this.invoice});

  final InvoiceResponse invoice;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(invoiceUpiQrProvider(invoice.invoiceId));
    final text = context.lpgText;
    final colors = context.lpgColors;

    return async.when(
      loading: () => const Padding(
        padding: EdgeInsets.all(LpgSpacing.xl),
        child: Center(child: LpgLoadingIndicator()),
      ),
      error: (err, _) => Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        mainAxisSize: MainAxisSize.min,
        children: [
          LpgBanner(tone: LpgTone.warning, message: errorMessage(err)),
          const SizedBox(height: LpgSpacing.sm),
          Text(
            'Set the agency UPI ID on the dashboard under Settings, Payments.',
            style: text.bodySmall?.copyWith(color: colors.textSecondary),
          ),
          const SizedBox(height: LpgSpacing.md),
          LpgButton(
            label: 'Try again',
            variant: LpgButtonVariant.secondary,
            expand: true,
            onPressed: () =>
                ref.invalidate(invoiceUpiQrProvider(invoice.invoiceId)),
          ),
        ],
      ),
      data: (qr) => Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        mainAxisSize: MainAxisSize.min,
        children: [
          LpgUpiQrCard(
            png: qr.png,
            amountText: LpgFormat.currency(qr.amount),
            payeeName: qr.payeeName,
            upiId: qr.upiId,
          ),
          const SizedBox(height: LpgSpacing.sm),
          Text(
            'Once the customer has paid, record it with "Record payment".',
            textAlign: TextAlign.center,
            style: text.bodySmall?.copyWith(color: colors.textSecondary),
          ),
        ],
      ),
    );
  }
}
