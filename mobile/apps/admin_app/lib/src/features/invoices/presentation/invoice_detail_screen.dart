import 'package:api_client/api_client.dart';
import 'package:core/core.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../api_result.dart';
import '../../../providers.dart';
import '../../../shared/invoice_tile.dart';
import '../../../shared/metric_tile.dart';
import '../../customers/data/customers_provider.dart';
import '../../dashboard/data/dashboard_providers.dart';
import '../../orders/data/orders_provider.dart';
import '../data/invoices_provider.dart';
import 'record_payment_sheet.dart';
import 'upi_qr_sheet.dart';

/// One invoice: who it is for, what it covers, the GST split, what has been
/// paid, and the three things an owner does with it: record a payment, show
/// the UPI QR, and send it (or a reminder) to the customer.
class InvoiceDetailScreen extends ConsumerStatefulWidget {
  const InvoiceDetailScreen({super.key, required this.invoiceId});

  final String invoiceId;

  @override
  ConsumerState<InvoiceDetailScreen> createState() =>
      _InvoiceDetailScreenState();
}

class _InvoiceDetailScreenState extends ConsumerState<InvoiceDetailScreen> {
  bool _busy = false;

  /// Reloads everything an invoice change shows up in.
  void _reload({String? customerId}) {
    ref.invalidate(invoiceDetailProvider(widget.invoiceId));
    ref.invalidate(invoicesProvider);
    ref.invalidate(operationsSnapshotProvider);
    if (customerId != null) {
      ref.invalidate(customerInvoicesProvider(customerId));
    }
  }

  Future<void> _recordPayment(InvoiceResponse invoice) async {
    final done = await LpgFeedback.showSheet<bool>(
      context,
      title: 'Record payment',
      builder: (_) => RecordPaymentSheet(invoice: invoice),
    );
    if (done != true || !mounted) return;
    _reload(customerId: invoice.customerId);
    LpgFeedback.showToast(context, 'Payment recorded.', tone: LpgTone.success);
  }

  Future<void> _showQr(InvoiceResponse invoice) => LpgFeedback.showSheet<void>(
    context,
    title: 'Pay by UPI',
    builder: (_) => UpiQrSheet(invoice: invoice),
  );

  Future<void> _send(InvoiceResponse invoice) async {
    setState(() => _busy = true);
    final result = await ref
        .read(invoiceApiProvider)
        .sendInvoice(invoice.invoiceId);
    if (!mounted) return;
    setState(() => _busy = false);
    switch (result) {
      case Success<InvoiceResponse>():
        LpgFeedback.showToast(
          context,
          'Invoice sent to the customer.',
          tone: LpgTone.success,
        );
      case FailureResult<InvoiceResponse>(:final failure):
        LpgFeedback.showToast(context, failure.message, tone: LpgTone.danger);
    }
  }

  @override
  Widget build(BuildContext context) {
    final async = ref.watch(invoiceDetailProvider(widget.invoiceId));

    return Scaffold(
      appBar: AppBar(
        title: Text(async.value?.invoiceNumber ?? 'Invoice'),
        actions: [
          IconButton(
            tooltip: 'Refresh',
            icon: const Icon(LpgIcons.sync),
            onPressed: _reload,
          ),
        ],
      ),
      body: async.when(
        loading: () => const Center(child: LpgLoadingIndicator()),
        error: (err, _) =>
            LpgErrorState(message: errorMessage(err), onRetry: _reload),
        data: _body,
      ),
    );
  }

  Widget _body(InvoiceResponse invoice) {
    final text = context.lpgText;
    final colors = context.lpgColors;
    final names = ref.watch(cylinderNamesProvider).value ?? const {};
    final severity = invoiceStatusSeverity(invoice.status);
    final cancelled = invoice.status == 'cancelled';
    final due = invoice.balanceDue;

    return RefreshIndicator(
      onRefresh: () async {
        _reload();
        await ref.read(invoiceDetailProvider(widget.invoiceId).future);
      },
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: LpgSpacing.page,
        children: [
          LpgCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        invoice.invoiceNumber ?? 'Invoice',
                        style: text.headlineSmall,
                      ),
                    ),
                    LpgStatusBadge(
                      label: LpgFormat.statusLabel(invoice.status),
                      severity: severity,
                    ),
                  ],
                ),
                const SizedBox(height: LpgSpacing.sm),
                InkWell(
                  onTap: () => context.pushNamed(
                    'customer_detail',
                    pathParameters: {'customerId': invoice.customerId},
                  ),
                  child: Padding(
                    padding: const EdgeInsets.symmetric(vertical: 2),
                    child: Row(
                      children: [
                        const Icon(LpgIcons.user, size: LpgSizes.iconSm),
                        const SizedBox(width: LpgSpacing.xs),
                        Expanded(
                          child: Text(
                            invoice.customerName ?? 'Customer',
                            style: text.bodyLarge,
                          ),
                        ),
                        const Icon(
                          LpgIcons.chevronRight,
                          size: LpgSizes.iconSm,
                        ),
                      ],
                    ),
                  ),
                ),
                if (invoice.orderNumber != null)
                  InkWell(
                    onTap: () => context.goNamed(
                      'order_detail',
                      pathParameters: {'orderId': invoice.orderId},
                    ),
                    child: Padding(
                      padding: const EdgeInsets.symmetric(vertical: 2),
                      child: Row(
                        children: [
                          const Icon(LpgIcons.orders, size: LpgSizes.iconSm),
                          const SizedBox(width: LpgSpacing.xs),
                          Expanded(
                            child: Text(
                              'Order ${invoice.orderNumber}',
                              style: text.bodyMedium?.copyWith(
                                color: colors.textSecondary,
                              ),
                            ),
                          ),
                          const Icon(
                            LpgIcons.chevronRight,
                            size: LpgSizes.iconSm,
                          ),
                        ],
                      ),
                    ),
                  ),
                const SizedBox(height: LpgSpacing.xs),
                Text(
                  'Issued ${LpgFormat.date(invoice.issuedAt)}'
                  '${invoice.customerGstin == null ? '' : '  ·  GSTIN ${invoice.customerGstin}'}',
                  style: text.bodySmall?.copyWith(color: colors.textSecondary),
                ),
              ],
            ),
          ),
          const SizedBox(height: LpgSpacing.md),
          MetricTile(
            label: cancelled ? 'Cancelled' : 'Balance due',
            value: cancelled ? '—' : LpgFormat.currency(due),
            caption: cancelled
                ? null
                : due > 0
                ? '${LpgFormat.currency(invoice.amountPaid)} paid of '
                      '${LpgFormat.currency(invoice.totalAmount)}'
                : 'Fully paid',
            icon: due > 0 && !cancelled ? LpgIcons.clock : LpgIcons.success,
            tone: cancelled
                ? LpgTone.danger
                : due > 0
                ? LpgTone.warning
                : LpgTone.success,
            attention: due > 0 && !cancelled,
          ),
          const SizedBox(height: LpgSpacing.md),
          if (!cancelled) ...[
            if (due > 0) ...[
              LpgButton(
                label: 'Record payment',
                icon: LpgIcons.rupee,
                expand: true,
                onPressed: _busy ? null : () => _recordPayment(invoice),
              ),
              const SizedBox(height: LpgSpacing.sm),
              LpgButton(
                label: 'Show UPI QR',
                icon: LpgIcons.qrCode,
                variant: LpgButtonVariant.secondary,
                expand: true,
                onPressed: _busy ? null : () => _showQr(invoice),
              ),
              const SizedBox(height: LpgSpacing.sm),
            ],
            LpgButton(
              label: due > 0 ? 'Send reminder' : 'Send to customer',
              icon: LpgIcons.share,
              variant: LpgButtonVariant.text,
              expand: true,
              isLoading: _busy,
              onPressed: _busy ? null : () => _send(invoice),
            ),
          ],
          const SectionHeading('Items', topGap: LpgSpacing.lg),
          LpgGroupedList(
            children: [
              for (final line in invoice.lines)
                LpgListTile(
                  leadingIcon: LpgIcons.cylinder,
                  title: names[line.cylinderTypeId] ?? 'Cylinder',
                  subtitle:
                      '${line.quantity} × ${LpgFormat.currency(line.unitPrice)}',
                  trailing: Text(
                    LpgFormat.currency(line.subtotal),
                    style: text.titleSmall,
                  ),
                ),
            ],
          ),
          const SizedBox(height: LpgSpacing.md),
          LpgCard(
            child: Column(
              children: [
                LpgKeyValueRow(
                  label: 'Subtotal',
                  value: LpgFormat.currency(invoice.subtotal),
                ),
                if (invoice.isInterState)
                  LpgKeyValueRow(
                    label: 'IGST',
                    value: LpgFormat.currency(invoice.igstAmount),
                  )
                else ...[
                  LpgKeyValueRow(
                    label: 'CGST',
                    value: LpgFormat.currency(invoice.cgstAmount),
                  ),
                  LpgKeyValueRow(
                    label: 'SGST',
                    value: LpgFormat.currency(invoice.sgstAmount),
                  ),
                ],
                if (invoice.cgstAmount == 0 &&
                    invoice.sgstAmount == 0 &&
                    invoice.igstAmount == 0)
                  LpgKeyValueRow(
                    label: 'Tax',
                    value: LpgFormat.currency(invoice.taxAmount),
                  ),
                LpgKeyValueRow(
                  label: 'Total',
                  value: LpgFormat.currency(invoice.totalAmount),
                  emphasize: true,
                ),
              ],
            ),
          ),
          const SectionHeading('Payments', topGap: LpgSpacing.lg),
          if (invoice.payments.isEmpty)
            Text(
              'No payments yet.',
              style: text.bodyMedium?.copyWith(color: colors.textSecondary),
            )
          else
            LpgGroupedList(
              children: [
                for (final p in invoice.payments)
                  LpgListTile(
                    leadingIcon: LpgIcons.payment,
                    leadingTone: LpgTone.success,
                    title: paymentMethodLabel(p.method),
                    subtitle: LpgFormat.dateTime(p.collectedAt),
                    trailing: Text(
                      LpgFormat.currency(p.amount),
                      style: text.titleSmall,
                    ),
                  ),
              ],
            ),
          const SizedBox(height: LpgSpacing.xl),
        ],
      ),
    );
  }
}

/// How a payment method reads.
String paymentMethodLabel(String method) => switch (method) {
  'cash' => 'Cash',
  'upi' => 'UPI',
  'card' => 'Card',
  'cheque' => 'Cheque',
  'bank_transfer' => 'Bank transfer',
  'online' => 'Online',
  _ => LpgFormat.sentence(method),
};
