import 'package:api_client/api_client.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../api_result.dart';
import '../../../shared/metric_tile.dart';
import '../../orders/data/orders_provider.dart';
import '../data/stock_provider.dart';
import 'count_review_sheet.dart';
import 'count_stock_sheet.dart';
import 'receive_stock_sheet.dart';
import 'stock_presentation.dart';

/// What a godown holds right now: filled cylinders per type with whatever
/// else is on the floor, anything running low, counts waiting to be
/// approved and the latest movements. From here the office books a truck in
/// from the OMC and counts the shelves.
class StockScreen extends ConsumerStatefulWidget {
  const StockScreen({super.key, this.initialGodownId});

  /// The godown to open on; the first one when `null`.
  final String? initialGodownId;

  @override
  ConsumerState<StockScreen> createState() => _StockScreenState();
}

class _StockScreenState extends ConsumerState<StockScreen> {
  String? _godownId;

  @override
  void initState() {
    super.initState();
    _godownId = widget.initialGodownId;
  }

  void _reload() {
    ref.invalidate(stockGodownsProvider);
    ref.invalidate(godownBalanceProvider);
    ref.invalidate(reorderSignalsProvider);
    ref.invalidate(godownMovementsProvider);
    ref.invalidate(pendingCountsProvider);
  }

  Future<void> _receive(FleetWarehouse godown) async {
    final received = await LpgFeedback.showSheet<GoodsReceipt>(
      context,
      title: 'Receive stock',
      builder: (_) => ReceiveStockSheet(godown: godown),
    );
    if (received == null || !mounted) return;
    _reload();
    LpgFeedback.showToast(
      context,
      '${received.quantity} cylinders received'
      '${received.grnNumber == null ? '' : ' · ${received.grnNumber}'}',
      tone: LpgTone.success,
    );
  }

  Future<void> _count(
    FleetWarehouse godown,
    List<StockBalanceLine> lines,
  ) async {
    final counted = await LpgFeedback.showSheet<bool>(
      context,
      title: 'Count stock',
      builder: (_) => CountStockSheet(godown: godown, lines: lines),
    );
    if (counted != true || !mounted) return;
    _reload();
    LpgFeedback.showToast(
      context,
      'Count recorded. Stock changes once it is approved.',
      tone: LpgTone.success,
    );
  }

  Future<void> _review(
    FleetWarehouse godown,
    ReconciliationRecord count,
  ) async {
    final decided = await LpgFeedback.showSheet<String>(
      context,
      title: 'Review count',
      builder: (_) => CountReviewSheet(count: count),
    );
    if (decided == null || !mounted) return;
    _reload();
    LpgFeedback.showToast(
      context,
      decided == 'approved'
          ? 'Count approved and booked into stock.'
          : 'Count rejected. Stock is unchanged.',
      tone: LpgTone.success,
    );
  }

  @override
  Widget build(BuildContext context) {
    final godowns = ref.watch(stockGodownsProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Stock'),
        actions: [
          IconButton(
            tooltip: 'Refresh',
            icon: const Icon(LpgIcons.sync),
            onPressed: _reload,
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: () async {
          _reload();
          await ref.read(stockGodownsProvider.future);
        },
        child: godowns.when(
          loading: () => const LpgSkeletonList(itemCount: 4),
          error: (err, _) => ListView(
            children: [
              LpgErrorState(message: errorMessage(err), onRetry: _reload),
            ],
          ),
          data: (list) {
            if (list.isEmpty) {
              return ListView(
                children: const [
                  LpgEmptyState(
                    icon: LpgIcons.warehouse,
                    title: 'No godown yet',
                    message:
                        'Add a godown on the dashboard to track its stock.',
                  ),
                ],
              );
            }
            final godown = list.firstWhere(
              (g) => g.id == _godownId,
              orElse: () => list.first,
            );
            return _GodownStock(
              godowns: list,
              godown: godown,
              onPick: (id) => setState(() => _godownId = id),
              onReceive: () => _receive(godown),
              onCount: (lines) => _count(godown, lines),
              onReview: (count) => _review(godown, count),
            );
          },
        ),
      ),
    );
  }
}

class _GodownStock extends ConsumerWidget {
  const _GodownStock({
    required this.godowns,
    required this.godown,
    required this.onPick,
    required this.onReceive,
    required this.onCount,
    required this.onReview,
  });

  final List<FleetWarehouse> godowns;
  final FleetWarehouse godown;
  final ValueChanged<String> onPick;
  final VoidCallback onReceive;
  final ValueChanged<List<StockBalanceLine>> onCount;
  final ValueChanged<ReconciliationRecord> onReview;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final balance = ref.watch(godownBalanceProvider(godown.id));
    final signals = ref.watch(reorderSignalsProvider).value ?? const [];
    final names = ref.watch(cylinderNamesProvider).value ?? const {};
    final catalog = ref.watch(cylinderCatalogProvider).value ?? const [];
    final low = [
      for (final s in signals)
        if (s.warehouseId == godown.id) s,
    ];

    return ListView(
      physics: const AlwaysScrollableScrollPhysics(),
      padding: LpgSpacing.page,
      children: [
        if (godowns.length > 1) ...[
          LpgDropdownField<String>(
            label: 'Godown',
            prefixIcon: LpgIcons.warehouse,
            value: godown.id,
            items: {for (final g in godowns) g.id: g.name},
            onChanged: (id) {
              if (id != null) onPick(id);
            },
          ),
          const SizedBox(height: LpgSpacing.md),
        ],
        balance.when(
          loading: () => const LpgSkeleton(height: 140),
          error: (err, _) => LpgErrorState(
            message: errorMessage(err),
            onRetry: () => ref.invalidate(godownBalanceProvider(godown.id)),
          ),
          data: (lines) {
            final types = groupByCylinderType(lines, [
              for (final t in catalog) t.id,
            ]);
            return _Holdings(
              godown: godown,
              types: types,
              names: names,
              low: low,
              onReceive: onReceive,
              onCount: () => onCount(lines),
            );
          },
        ),
        const SectionHeading(
          'Counts waiting for approval',
          topGap: LpgSpacing.lg,
        ),
        _PendingCounts(godownId: godown.id, names: names, onReview: onReview),
        const SectionHeading('Latest movements', topGap: LpgSpacing.lg),
        _Movements(godownId: godown.id, names: names),
        const SizedBox(height: LpgSpacing.xl),
      ],
    );
  }
}

class _Holdings extends StatelessWidget {
  const _Holdings({
    required this.godown,
    required this.types,
    required this.names,
    required this.low,
    required this.onReceive,
    required this.onCount,
  });

  final FleetWarehouse godown;
  final List<TypeStock> types;
  final Map<String, String> names;
  final List<ReorderSignal> low;
  final VoidCallback onReceive;
  final VoidCallback onCount;

  @override
  Widget build(BuildContext context) {
    final text = context.lpgText;
    final colors = context.lpgColors;
    final filled = types.fold<int>(0, (sum, t) => sum + t.filled);
    ReorderSignal? signalFor(String typeId) {
      for (final s in low) {
        if (s.cylinderTypeId == typeId) return s;
      }
      return null;
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        LpgHeroCard(
          watermark: LpgIcons.warehouse,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Filled cylinders ready to send',
                style: text.bodyMedium?.copyWith(color: colors.onHero),
              ),
              const SizedBox(height: LpgSpacing.xs),
              Text(
                '$filled',
                style: text.headlineLarge?.copyWith(color: colors.onHero),
              ),
              const SizedBox(height: LpgSpacing.xs),
              Text(
                godown.name,
                style: text.bodySmall?.copyWith(color: colors.onHero),
              ),
            ],
          ),
        ),
        const SizedBox(height: LpgSpacing.md),
        Row(
          children: [
            Expanded(
              child: LpgButton(
                label: 'Receive stock',
                icon: LpgIcons.download,
                expand: true,
                onPressed: onReceive,
              ),
            ),
            const SizedBox(width: LpgSpacing.md),
            Expanded(
              child: LpgButton(
                label: 'Count stock',
                icon: LpgIcons.check,
                variant: LpgButtonVariant.secondary,
                expand: true,
                onPressed: onCount,
              ),
            ),
          ],
        ),
        for (final s in low) ...[
          const SizedBox(height: LpgSpacing.md),
          LpgBanner(
            tone: s.isCritical ? LpgTone.danger : LpgTone.warning,
            icon: LpgIcons.warning,
            title:
                '${names[s.cylinderTypeId] ?? 'A cylinder type'} is running low',
            message:
                '${s.onHand} filled left, reorder at ${s.reorderPoint}'
                '${s.isCritical ? '. Nearly out.' : '.'}',
          ),
        ],
        const SectionHeading('By cylinder type', topGap: LpgSpacing.lg),
        if (types.isEmpty)
          Text(
            'Nothing is recorded at this godown yet. Receive a truck to start.',
            style: text.bodyMedium?.copyWith(color: colors.textSecondary),
          )
        else
          LpgGroupedList(
            children: [
              for (final t in types)
                LpgListTile(
                  leadingIcon: LpgIcons.cylinder,
                  leadingTone: signalFor(t.cylinderTypeId) == null
                      ? LpgTone.primary
                      : LpgTone.danger,
                  title: names[t.cylinderTypeId] ?? 'Cylinder',
                  subtitle: t.others.isEmpty
                      ? 'No other stock'
                      : [
                          for (final o in t.others)
                            '${stockStatusLabel(o.key)} ${o.value}',
                        ].join(' · '),
                  trailing: Column(
                    mainAxisSize: MainAxisSize.min,
                    crossAxisAlignment: CrossAxisAlignment.end,
                    children: [
                      Text(
                        '${t.filled}',
                        style: text.titleMedium?.copyWith(
                          color: signalFor(t.cylinderTypeId) == null
                              ? null
                              : colors.statusDanger,
                        ),
                      ),
                      Text(
                        'filled',
                        style: text.bodySmall?.copyWith(
                          color: colors.textSecondary,
                        ),
                      ),
                    ],
                  ),
                ),
            ],
          ),
      ],
    );
  }
}

class _PendingCounts extends ConsumerWidget {
  const _PendingCounts({
    required this.godownId,
    required this.names,
    required this.onReview,
  });

  final String godownId;
  final Map<String, String> names;
  final ValueChanged<ReconciliationRecord> onReview;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final text = context.lpgText;
    final colors = context.lpgColors;
    final counts = ref.watch(pendingCountsProvider(godownId));

    return counts.when(
      loading: () => const LpgSkeleton(height: 72),
      error: (err, _) => Text(
        errorMessage(err),
        style: text.bodyMedium?.copyWith(color: colors.statusDanger),
      ),
      data: (list) {
        if (list.isEmpty) {
          return Text(
            'No counts are waiting.',
            style: text.bodyMedium?.copyWith(color: colors.textSecondary),
          );
        }
        return LpgGroupedList(
          children: [
            for (final c in list)
              LpgListTile(
                leadingIcon: LpgIcons.pending,
                leadingTone: LpgTone.warning,
                title:
                    '${names[c.cylinderTypeId] ?? 'Cylinder'} · ${stockStatusLabel(c.status)}',
                subtitle:
                    'System ${c.expectedQuantity}, counted ${c.actualQuantity}',
                trailing: Text(
                  c.variance == 0
                      ? 'Matches'
                      : '${c.variance > 0 ? '+' : ''}${c.variance}',
                  style: text.titleSmall?.copyWith(
                    color: c.variance == 0
                        ? colors.textSecondary
                        : (c.variance < 0
                              ? colors.statusDanger
                              : colors.statusInfo),
                  ),
                ),
                showChevron: true,
                onTap: () => onReview(c),
              ),
          ],
        );
      },
    );
  }
}

class _Movements extends ConsumerWidget {
  const _Movements({required this.godownId, required this.names});

  final String godownId;
  final Map<String, String> names;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final text = context.lpgText;
    final colors = context.lpgColors;
    final moves = ref.watch(godownMovementsProvider(godownId));

    return moves.when(
      loading: () => const LpgSkeleton(height: 96),
      error: (err, _) => Text(
        errorMessage(err),
        style: text.bodyMedium?.copyWith(color: colors.statusDanger),
      ),
      data: (list) {
        if (list.isEmpty) {
          return Text(
            'Nothing has moved at this godown yet.',
            style: text.bodyMedium?.copyWith(color: colors.textSecondary),
          );
        }
        return LpgGroupedList(
          children: [
            for (final m in list)
              LpgListTile(
                leadingIcon: movementIcon(m.type),
                title: movementLabel(m.type),
                subtitle:
                    '${names[m.cylinderTypeId] ?? 'Cylinder'} · ${movementStatus(m)}'
                    ' · ${LpgFormat.relative(m.performedAt)}',
                trailing: Text(
                  signedQuantity(m),
                  style: text.titleSmall?.copyWith(
                    color: switch (movementDirection(m)) {
                      1 => colors.statusSuccess,
                      -1 => colors.statusDanger,
                      _ => null,
                    },
                  ),
                ),
              ),
          ],
        );
      },
    );
  }
}
