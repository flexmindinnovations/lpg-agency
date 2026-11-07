import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../payments/presentation/pay_online_section.dart';
import '../data/cylinder_types_provider.dart';
import '../data/invoices_provider.dart';
import '../../../i18n/customer_strings.dart';
import 'invoice_paper.dart';
import 'invoice_pdf.dart';

class InvoiceDetailScreen extends ConsumerWidget {
  const InvoiceDetailScreen({super.key, required this.invoiceId});

  final String invoiceId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final invoiceAsync = ref.watch(invoiceDetailProvider(invoiceId));

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
            InvoicePaper(invoice: invoice, cylinderNames: cylinderNames),
            const SizedBox(height: LpgSpacing.lg),
            LpgButton(
              label: context.strings.invoice.download,
              icon: LpgIcons.download,
              variant: LpgButtonVariant.secondary,
              expand: true,
              onPressed: () async {
                try {
                  await shareInvoicePdf(
                    invoice,
                    cylinderNames: cylinderNames,
                    s: context.strings,
                  );
                } catch (e) {
                  if (context.mounted) {
                    LpgFeedback.showToast(
                      context,
                      context.strings.invoice.downloadFailed,
                      tone: LpgTone.danger,
                    );
                  }
                }
              },
            ),
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
