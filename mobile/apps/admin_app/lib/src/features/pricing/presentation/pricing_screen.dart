import 'package:api_client/api_client.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../api_result.dart';
import '../../../shared/metric_tile.dart';
import '../../fleet/data/fleet_providers.dart';
import '../../orders/data/orders_provider.dart';
import '../data/pricing_provider.dart';
import 'pricing_presentation.dart';
import 'proposal_sheet.dart';
import 'set_price_sheet.dart';

/// What each cylinder type costs each kind of customer, per branch where a
/// branch has its own price. Tap a price to change it, add one that is
/// missing, and review the oil companies' rate changes waiting at the top.
class PricingScreen extends ConsumerWidget {
  const PricingScreen({super.key});

  void _reload(WidgetRef ref) {
    ref.invalidate(priceEntriesProvider);
    ref.invalidate(priceProposalsProvider);
    ref.invalidate(cylinderCatalogProvider);
    ref.invalidate(fleetBranchesProvider);
  }

  Future<void> _setPrice(
    BuildContext context,
    WidgetRef ref, [
    PriceRow? row,
  ]) async {
    final saved = await LpgFeedback.showSheet<bool>(
      context,
      title: row == null ? 'Add a price' : 'Change price',
      builder: (_) => SetPriceSheet(row: row),
    );
    if (saved != true || !context.mounted) return;
    _reload(ref);
    LpgFeedback.showToast(context, 'Price saved.', tone: LpgTone.success);
  }

  Future<void> _review(
    BuildContext context,
    WidgetRef ref,
    PriceProposal proposal,
    double? currentPrice,
  ) async {
    final decided = await LpgFeedback.showSheet<String>(
      context,
      title: 'OMC rate change',
      builder: (_) =>
          ProposalSheet(proposal: proposal, currentPrice: currentPrice),
    );
    if (decided == null || !context.mounted) return;
    _reload(ref);
    LpgFeedback.showToast(
      context,
      decided == 'accepted'
          ? 'Accepted. The new price is on the list.'
          : 'Rejected. Prices are unchanged.',
      tone: LpgTone.success,
    );
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final prices = ref.watch(priceEntriesProvider);
    final proposals = ref.watch(priceProposalsProvider).value ?? const [];
    final catalog = ref.watch(cylinderCatalogProvider).value ?? const [];
    final names = {for (final t in catalog) t.id: t.name};
    final branches = {
      for (final b in ref.watch(fleetBranchesProvider).value ?? const [])
        b.id: b.name,
    };

    return Scaffold(
      appBar: AppBar(
        title: const Text('Pricing'),
        actions: [
          IconButton(
            tooltip: 'Refresh',
            icon: const Icon(LpgIcons.sync),
            onPressed: () => _reload(ref),
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: () async {
          _reload(ref);
          await ref.read(priceEntriesProvider.future);
        },
        child: prices.when(
          loading: () => const LpgSkeletonList(itemCount: 5),
          error: (err, _) => ListView(
            children: [
              LpgErrorState(
                message: errorMessage(err),
                onRetry: () => _reload(ref),
              ),
            ],
          ),
          data: (entries) {
            final rows = buildPriceRows(entries, [
              for (final t in catalog) t.id,
            ]);
            final byType = <String, List<PriceRow>>{};
            for (final r in rows) {
              byType.putIfAbsent(r.cylinderTypeId, () => []).add(r);
            }
            double? currentFor(PriceProposal p) {
              for (final r in rows) {
                if (r.cylinderTypeId == p.cylinderTypeId &&
                    r.customerType == p.customerType &&
                    r.branchId == p.branchId) {
                  return r.current()?.price;
                }
              }
              return null;
            }

            return ListView(
              physics: const AlwaysScrollableScrollPhysics(),
              padding: LpgSpacing.page,
              children: [
                if (proposals.isNotEmpty) ...[
                  SectionHeading(
                    'Rate changes to review (${proposals.length})',
                  ),
                  LpgGroupedList(
                    children: [
                      for (final p in proposals)
                        LpgListTile(
                          leadingIcon: LpgIcons.trendUp,
                          leadingTone: LpgTone.warning,
                          title:
                              '${names[p.cylinderTypeId] ?? 'Cylinder'} · ${customerTypeLabel(p.customerType)}',
                          subtitle:
                              'From ${LpgFormat.shortDate(p.effectiveFrom)}',
                          trailing: Text(
                            LpgFormat.currency(p.proposedPrice),
                            style: context.lpgText.titleSmall,
                          ),
                          showChevron: true,
                          onTap: () => _review(context, ref, p, currentFor(p)),
                        ),
                    ],
                  ),
                ],
                SectionHeading(
                  'Prices',
                  topGap: proposals.isEmpty ? 0 : LpgSpacing.lg,
                  actionLabel: 'Add price',
                  onAction: () => _setPrice(context, ref),
                ),
                if (rows.isEmpty)
                  const LpgEmptyState(
                    icon: LpgIcons.rupee,
                    title: 'No prices yet',
                    message:
                        'Add a price for each cylinder type and customer type.',
                  )
                else
                  for (final entry in byType.entries) ...[
                    Padding(
                      padding: const EdgeInsets.only(
                        top: LpgSpacing.md,
                        bottom: LpgSpacing.sm,
                      ),
                      child: Text(
                        names[entry.key] ?? 'Cylinder',
                        style: context.lpgText.titleSmall?.copyWith(
                          color: context.lpgColors.textSecondary,
                        ),
                      ),
                    ),
                    LpgGroupedList(
                      children: [
                        for (final r in entry.value)
                          _PriceTile(
                            row: r,
                            branchName: r.branchId == null
                                ? null
                                : branches[r.branchId] ?? 'Branch',
                            onTap: () => _setPrice(context, ref, r),
                          ),
                      ],
                    ),
                  ],
                const SizedBox(height: LpgSpacing.xl),
              ],
            );
          },
        ),
      ),
    );
  }
}

class _PriceTile extends StatelessWidget {
  const _PriceTile({
    required this.row,
    required this.branchName,
    required this.onTap,
  });

  final PriceRow row;
  final String? branchName;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final text = context.lpgText;
    final colors = context.lpgColors;
    final current = row.current();
    final next = row.upcoming().firstOrNull;
    // Before the first price starts, show what is coming instead of nothing.
    final shown = current ?? next;

    final subtitle = switch ((current, next)) {
      (_, final PriceEntry n) when current != null =>
        'Changes to ${LpgFormat.currency(n.price)} on ${LpgFormat.shortDate(n.effectiveFrom)}',
      (null, final PriceEntry n) =>
        'Starts ${LpgFormat.shortDate(n.effectiveFrom)}',
      (final PriceEntry c, _) =>
        'Since ${LpgFormat.shortDate(c.effectiveFrom)}',
      _ => null,
    };

    return LpgListTile(
      leadingIcon: branchName == null ? LpgIcons.customers : LpgIcons.agency,
      title: branchName == null
          ? customerTypeLabel(row.customerType)
          : '${customerTypeLabel(row.customerType)} · $branchName',
      subtitle: subtitle,
      trailing: Text(
        shown == null ? '' : LpgFormat.currency(shown.price),
        style: text.titleMedium?.copyWith(
          color: current == null ? colors.textSecondary : null,
        ),
      ),
      showChevron: true,
      onTap: onTap,
    );
  }
}
