import 'package:api_client/api_client.dart';
import 'package:core/core.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../providers.dart';
import '../../../shared/invoice_tile.dart';
import '../../../shared/metric_tile.dart';
import '../../invoices/presentation/invoice_detail_screen.dart';

/// How a delivered order ended: the delivery record and the invoice.
class OrderSettlementData {
  const OrderSettlementData({this.proof, this.invoice});

  final ProofOfDelivery? proof;
  final InvoiceResponse? invoice;
}

/// The delivery record and the invoice for an order. A role that may not see
/// one of them simply gets that part empty rather than an error.
final orderSettlementProvider =
    FutureProvider.family<OrderSettlementData, String>((ref, orderId) async {
      final results = await (
        ref.watch(orderApiProvider).getProofOfDelivery(orderId),
        ref
            .watch(invoiceApiProvider)
            .getMyInvoices(orderId: orderId, pageSize: 1),
      ).wait;
      return OrderSettlementData(
        proof: switch (results.$1) {
          Success<ProofOfDelivery?>(:final value) => value,
          _ => null,
        },
        invoice: switch (results.$2) {
          Success<InvoicePageResponse>(:final value) =>
            value.items.isEmpty ? null : value.items.first,
          _ => null,
        },
      );
    });

/// What happened at the door and how the money stands: when it was
/// delivered, what was collected, where, the signature and photo, and the
/// order's invoice with a way into it.
class OrderSettlement extends ConsumerWidget {
  const OrderSettlement({super.key, required this.order});

  final OrderResponse order;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final data = ref.watch(orderSettlementProvider(order.id));
    return data.when(
      loading: () => const Padding(
        padding: EdgeInsets.only(top: LpgSpacing.lg),
        child: LpgSkeleton(height: 120),
      ),
      error: (_, _) => const SizedBox.shrink(),
      data: (d) => Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (d.proof != null) _Delivery(proof: d.proof!),
          _Payment(order: order, proof: d.proof, invoice: d.invoice),
        ],
      ),
    );
  }
}

class _Delivery extends StatelessWidget {
  const _Delivery({required this.proof});

  final ProofOfDelivery proof;

  Future<void> _openMap(BuildContext context) async {
    final uri = Uri.parse(
      'https://www.google.com/maps/search/?api=1&query=${proof.gpsLat},${proof.gpsLng}',
    );
    if (!await launchUrl(uri, mode: LaunchMode.externalApplication) &&
        context.mounted) {
      LpgFeedback.showToast(
        context,
        'Could not open the map.',
        tone: LpgTone.danger,
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final text = context.lpgText;
    final signature = proof.signatureUrl;
    final photo = proof.photoUrl;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const SectionHeading('Delivery', topGap: LpgSpacing.lg),
        LpgGroupedList(
          children: [
            LpgListTile(
              leadingIcon: LpgIcons.success,
              leadingTone: LpgTone.success,
              title: 'Delivered',
              trailing: Text(
                LpgFormat.dateTime(proof.recordedAt.toLocal()),
                style: text.titleSmall,
              ),
            ),
            LpgListTile(
              leadingIcon: LpgIcons.cash,
              title: 'Collected at the door',
              subtitle: paymentMethodLabel(proof.paymentMethod),
              trailing: Text(
                LpgFormat.currency(proof.amountCollected),
                style: text.titleSmall,
              ),
            ),
            LpgListTile(
              leadingIcon: LpgIcons.location,
              title: 'Where it was delivered',
              subtitle: 'Open on the map',
              showChevron: true,
              onTap: () => _openMap(context),
            ),
            if (proof.dacCode != null)
              LpgListTile(
                leadingIcon: LpgIcons.security,
                title: 'Delivery code from the OMC',
                trailing: Text(proof.dacCode!, style: text.titleSmall),
              ),
          ],
        ),
        if (signature != null || photo != null) ...[
          const SizedBox(height: LpgSpacing.md),
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              if (signature != null)
                Expanded(
                  child: _Evidence(label: 'Signature', url: signature),
                ),
              if (signature != null && photo != null)
                const SizedBox(width: LpgSpacing.md),
              if (photo != null)
                Expanded(
                  child: _Evidence(label: 'Photo', url: photo),
                ),
            ],
          ),
        ],
      ],
    );
  }
}

/// A signature or photo as a small picture that opens full size.
class _Evidence extends StatelessWidget {
  const _Evidence({required this.label, required this.url});

  final String label;
  final String url;

  Widget _image(BoxFit fit) => Image.network(
    url,
    fit: fit,
    errorBuilder: (_, _, _) => const Center(child: Icon(LpgIcons.imageBroken)),
  );

  @override
  Widget build(BuildContext context) {
    final text = context.lpgText;
    final colors = context.lpgColors;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: text.bodySmall?.copyWith(color: colors.textSecondary),
        ),
        const SizedBox(height: LpgSpacing.xs),
        Semantics(
          button: true,
          label: 'Show the $label full size',
          child: InkWell(
            borderRadius: BorderRadius.circular(LpgRadius.lg),
            onTap: () => showDialog<void>(
              context: context,
              builder: (_) => Dialog(
                child: InteractiveViewer(child: _image(BoxFit.contain)),
              ),
            ),
            child: ClipRRect(
              borderRadius: BorderRadius.circular(LpgRadius.lg),
              child: ColoredBox(
                color: colors.card,
                child: SizedBox(height: 120, child: _image(BoxFit.cover)),
              ),
            ),
          ),
        ),
      ],
    );
  }
}

class _Payment extends StatelessWidget {
  const _Payment({
    required this.order,
    required this.proof,
    required this.invoice,
  });

  final OrderResponse order;
  final ProofOfDelivery? proof;
  final InvoiceResponse? invoice;

  @override
  Widget build(BuildContext context) {
    final text = context.lpgText;
    final colors = context.lpgColors;
    final inv = invoice;
    final collected = proof?.amountCollected;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const SectionHeading('Payment and invoice', topGap: LpgSpacing.lg),
        if (inv == null)
          Text(
            'No invoice for this order yet.',
            style: text.bodyMedium?.copyWith(color: colors.textSecondary),
          )
        else ...[
          LpgGroupedList(
            children: [
              InvoiceTile(
                invoice: inv,
                onTap: () => context.pushNamed(
                  'invoice_detail',
                  pathParameters: {'invoiceId': inv.invoiceId},
                ),
              ),
            ],
          ),
          const SizedBox(height: LpgSpacing.sm),
          LpgCard(
            child: Column(
              children: [
                LpgKeyValueRow(
                  label: 'Invoice total',
                  value: LpgFormat.currency(inv.totalAmount),
                ),
                LpgKeyValueRow(
                  label: 'Paid so far',
                  value: LpgFormat.currency(inv.amountPaid),
                ),
                LpgKeyValueRow(
                  label: 'Still due',
                  value: LpgFormat.currency(inv.balanceDue),
                  emphasize: inv.balanceDue > 0,
                  valueColor: inv.balanceDue > 0 ? colors.statusDanger : null,
                ),
              ],
            ),
          ),
          if (collected != null && inv.balanceDue >= 0.01) ...[
            const SizedBox(height: LpgSpacing.sm),
            LpgBanner(
              tone: LpgTone.info,
              message:
                  'The driver collected ${LpgFormat.currency(collected)} at the door; '
                  'the invoice is ${LpgFormat.currency(inv.totalAmount)} and '
                  '${LpgFormat.currency(inv.balanceDue)} is still due. '
                  'Open the invoice to record a payment.',
            ),
          ],
        ],
      ],
    );
  }
}
