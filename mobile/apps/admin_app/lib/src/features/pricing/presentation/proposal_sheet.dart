import 'package:api_client/api_client.dart';
import 'package:core/core.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../providers.dart';
import '../../fleet/data/fleet_providers.dart';
import '../../orders/data/orders_provider.dart';
import 'pricing_presentation.dart';

/// One rate change an oil company announced: today's price next to the
/// proposed one, with where the number came from. Accepting adds it to the
/// price list from its start date; rejecting leaves prices alone. Pops
/// `accepted` or `rejected`.
class ProposalSheet extends ConsumerStatefulWidget {
  const ProposalSheet({super.key, required this.proposal, this.currentPrice});

  final PriceProposal proposal;

  /// What this cylinder, customer type and branch costs today, when known.
  final double? currentPrice;

  @override
  ConsumerState<ProposalSheet> createState() => _ProposalSheetState();
}

class _ProposalSheetState extends ConsumerState<ProposalSheet> {
  String? _error;
  bool _busy = false;

  Future<void> _decide(bool accept) async {
    setState(() {
      _busy = true;
      _error = null;
    });
    final result = await ref
        .read(priceListApiProvider)
        .reviewProposal(widget.proposal.id, accept: accept);
    if (!mounted) return;
    switch (result) {
      case Success<void>():
        Navigator.of(context).pop(accept ? 'accepted' : 'rejected');
      case FailureResult<void>(:final failure):
        setState(() {
          _busy = false;
          _error = failure.message;
        });
    }
  }

  Future<void> _openSource() async {
    final uri = Uri.tryParse(widget.proposal.sourceUrl);
    final opened = uri != null && await launchUrl(uri);
    if (!opened && mounted) {
      setState(() => _error = 'Could not open the link.');
    }
  }

  @override
  Widget build(BuildContext context) {
    final p = widget.proposal;
    final text = context.lpgText;
    final colors = context.lpgColors;
    final names = ref.watch(cylinderNamesProvider).value ?? const {};
    final branches = {
      for (final b in ref.watch(fleetBranchesProvider).value ?? const [])
        b.id: b.name,
    };
    final current = widget.currentPrice;

    return SingleChildScrollView(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            '${names[p.cylinderTypeId] ?? 'Cylinder'} · ${customerTypeLabel(p.customerType)}'
            '${p.branchId == null ? '' : ' · ${branches[p.branchId] ?? 'Branch'}'}',
            style: text.titleMedium,
          ),
          const SizedBox(height: LpgSpacing.md),
          LpgGroupedList(
            children: [
              LpgListTile(
                title: 'Price now',
                trailing: Text(
                  current == null ? 'Not set' : LpgFormat.currency(current),
                  style: text.titleSmall,
                ),
              ),
              LpgListTile(
                title: 'Proposed',
                subtitle: 'From ${LpgFormat.date(p.effectiveFrom)}',
                trailing: Text(
                  current == null
                      ? LpgFormat.currency(p.proposedPrice)
                      : '${LpgFormat.currency(p.proposedPrice)}  ${changeLabel(current, p.proposedPrice)}',
                  style: text.titleSmall,
                ),
              ),
            ],
          ),
          if (p.sourceUrl.isNotEmpty) ...[
            const SizedBox(height: LpgSpacing.md),
            LpgListTile(
              leadingIcon: LpgIcons.external,
              title: 'Check where it came from',
              subtitle: p.sourceUrl,
              onTap: _openSource,
            ),
          ],
          const SizedBox(height: LpgSpacing.sm),
          Text(
            'Accepting adds this to the price list. Rejecting leaves prices as they are.',
            style: text.bodySmall?.copyWith(color: colors.textSecondary),
          ),
          if (_error != null) ...[
            const SizedBox(height: LpgSpacing.sm),
            LpgBanner(tone: LpgTone.danger, message: _error!),
          ],
          const SizedBox(height: LpgSpacing.lg),
          LpgButton(
            label: 'Accept new price',
            icon: LpgIcons.check,
            isLoading: _busy,
            expand: true,
            onPressed: _busy ? null : () => _decide(true),
          ),
          const SizedBox(height: LpgSpacing.sm),
          LpgButton(
            label: 'Reject',
            variant: LpgButtonVariant.secondary,
            expand: true,
            onPressed: _busy ? null : () => _decide(false),
          ),
        ],
      ),
    );
  }
}
