import 'package:api_client/api_client.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../offline/delivery_mutations.dart';
import '../../../offline/pending_sync.dart';
import '../../delivery/data/active_route_provider.dart';
import '../data/cash_handover_provider.dart';

/// End-of-route cash reconciliation. Reached from the Today "reconcile your
/// cash" nudge and the Deliveries "Past routes" list — a full-screen task
/// above the shell, like the stop-detail drill-in.
///
/// The route is gone from `activeRouteProvider` by the time this matters
/// (it only becomes relevant once the route is `completed`), so this screen
/// reads everything it needs from `GET /cash-handovers/for-route/{id}`.
class CashHandoverScreen extends ConsumerStatefulWidget {
  const CashHandoverScreen({super.key, required this.routeId});

  final String routeId;

  @override
  ConsumerState<CashHandoverScreen> createState() => _CashHandoverScreenState();
}

class _CashHandoverScreenState extends ConsumerState<CashHandoverScreen> {
  final _amountController = TextEditingController();
  bool _submitting = false;
  String? _error;

  @override
  void dispose() {
    _amountController.dispose();
    super.dispose();
  }

  double? get _entered => double.tryParse(_amountController.text.trim());

  Future<void> _declare(RouteCashHandover view) async {
    final amount = _entered;
    if (amount == null || amount < 0) {
      setState(() => _error = 'Enter the amount you are handing over.');
      return;
    }

    final confirmed = await LpgFeedback.confirm(
      context,
      title: 'Confirm cash handover',
      message:
          'Hand over ${_money(amount)} for the '
          '${LpgFormat.date(view.routeDate)} route? This cannot be undone.',
    );
    if (confirmed != true || !mounted) return;

    setState(() {
      _submitting = true;
      _error = null;
    });

    try {
      await ref
          .read(deliveryMutationsProvider)
          .declareCashHandover(
            routeId: widget.routeId,
            driverId: view.driverId,
            actualAmount: amount,
          );
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _submitting = false;
        _error = "Couldn't queue the handover: $e";
      });
      return;
    }
    if (!mounted) return;

    // The declaration is now a queued op; the screen flips to the "queued"
    // notice via `pendingSyncAggregatesProvider`. Once it syncs the provider
    // re-fetches and shows the real receipt.
    ref.invalidate(pendingCashHandoverProvider);
    ref.invalidate(routeHistoryProvider);
    LpgFeedback.showToast(
      context,
      'Cash handover submitted.',
      tone: LpgTone.success,
    );
    setState(() => _submitting = false);
  }

  @override
  Widget build(BuildContext context) {
    final viewAsync = ref.watch(routeCashHandoverProvider(widget.routeId));

    return Scaffold(
      appBar: AppBar(title: const Text('Cash handover')),
      body: viewAsync.when(
        loading: () => const LpgSkeletonList(itemCount: 3),
        error: (err, _) => LpgErrorState(
          message: 'Could not load this route.\n$err',
          onRetry: () =>
              ref.invalidate(routeCashHandoverProvider(widget.routeId)),
        ),
        data: (view) {
          final queued =
              ref
                  .watch(pendingSyncAggregatesProvider)
                  .value
                  ?.contains(widget.routeId) ??
              false;
          if (queued && view.handover == null) {
            return const _QueuedNotice();
          }
          if (view.handover != null) {
            return _Receipt(view: view, handover: view.handover!);
          }
          if (view.routeStatus != 'completed') {
            return const LpgEmptyState(
              title: 'Route in progress',
              message:
                  'This route is still in progress. Reconcile the cash once '
                  'every stop is done.',
              icon: LpgIcons.pending,
              tone: LpgTone.warning,
            );
          }
          return _DeclareForm(
            view: view,
            amountController: _amountController,
            entered: _entered,
            error: _error,
            submitting: _submitting,
            onAmountChanged: () => setState(() => _error = null),
            onDeclare: () => _declare(view),
          );
        },
      ),
    );
  }
}

String _money(double v) => LpgFormat.currency(v);

/// Shown after a declaration is queued but hasn't synced yet.
class _QueuedNotice extends StatelessWidget {
  const _QueuedNotice();

  @override
  Widget build(BuildContext context) => const LpgEmptyState(
    title: 'Queued',
    message: 'Cash handover submitted.\nIt will sync once you are back online.',
    icon: LpgIcons.upload,
    tone: LpgTone.info,
  );
}

class _DeclareForm extends StatelessWidget {
  const _DeclareForm({
    required this.view,
    required this.amountController,
    required this.entered,
    required this.error,
    required this.submitting,
    required this.onAmountChanged,
    required this.onDeclare,
  });

  final RouteCashHandover view;
  final TextEditingController amountController;
  final double? entered;
  final String? error;
  final bool submitting;
  final VoidCallback onAmountChanged;
  final VoidCallback onDeclare;

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;
    final text = context.lpgText;
    final stops = view.cashStopCount;

    return ListView(
      padding: LpgSpacing.page,
      children: [
        if (error != null) ...[
          LpgBanner(tone: LpgTone.danger, message: error!),
          const SizedBox(height: LpgSpacing.md),
        ],
        LpgFadeSlideIn(
          child: LpgHeroCard(
            watermark: LpgIcons.wallet,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Expected cash · ${LpgFormat.date(view.routeDate)} route',
                  style: text.titleSmall?.copyWith(color: colors.onHero),
                ),
                const SizedBox(height: LpgSpacing.sm),
                Text(
                  _money(view.expectedAmount),
                  style: text.displaySmall?.copyWith(color: colors.onHero),
                ),
                const SizedBox(height: LpgSpacing.xs),
                Text(
                  'from $stops cash ${stops == 1 ? 'delivery' : 'deliveries'} '
                  'on this route',
                  style: text.bodyMedium?.copyWith(color: colors.onHero),
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: LpgSpacing.lg),
        LpgTextField(
          label: 'Amount handed over',
          isRequired: true,
          prefixIcon: LpgIcons.rupee,
          controller: amountController,
          keyboardType: const TextInputType.numberWithOptions(decimal: true),
          onChanged: (_) => onAmountChanged(),
        ),
        const SizedBox(height: LpgSpacing.sm),
        _DeltaLine(expected: view.expectedAmount, entered: entered),
        const SizedBox(height: LpgSpacing.xl),
        LpgButton(
          label: 'Declare handover',
          icon: LpgIcons.handover,
          expand: true,
          isLoading: submitting,
          onPressed: submitting ? null : onDeclare,
        ),
      ],
    );
  }
}

class _DeltaLine extends StatelessWidget {
  const _DeltaLine({required this.expected, required this.entered});

  final double expected;
  final double? entered;

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;
    final text = context.lpgText;
    final value = entered;

    if (value == null) {
      return Text(
        'Count the cash and enter the total.',
        style: text.bodySmall?.copyWith(color: colors.textSecondary),
      );
    }

    final diff = value - expected;
    final (String label, LpgTone tone, IconData icon) = switch (diff) {
      _ when diff.abs() < 0.005 => (
        'Matches the expected ${_money(expected)}',
        LpgTone.success,
        LpgIcons.successFilled,
      ),
      _ when diff < 0 => (
        'Short by ${_money(-diff)}',
        LpgTone.danger,
        LpgIcons.warning,
      ),
      _ => ('Over by ${_money(diff)}', LpgTone.warning, LpgIcons.info),
    };
    final color = tone.foreground(colors);

    return Semantics(
      liveRegion: true,
      child: Row(
        children: [
          Icon(icon, size: LpgSizes.iconSm, color: color),
          const SizedBox(width: LpgSpacing.sm),
          Text(label, style: text.labelLarge?.copyWith(color: color)),
        ],
      ),
    );
  }
}

class _Receipt extends StatelessWidget {
  const _Receipt({required this.view, required this.handover});

  final RouteCashHandover view;
  final CashHandover handover;

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;
    final short = handover.shortfall > 0;
    final over = handover.surplus > 0;

    return ListView(
      padding: LpgSpacing.page,
      children: [
        LpgFadeSlideIn(
          child: LpgCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    const LpgIconBox(icon: LpgIcons.receipt),
                    const SizedBox(width: LpgSpacing.smd),
                    Expanded(
                      child: Text(
                        handover.handoverNumber ?? 'Cash handover',
                        style: context.lpgText.titleMedium,
                      ),
                    ),
                    LpgStatusBadge(
                      label: short
                          ? 'SHORT'
                          : over
                          ? 'OVER'
                          : 'RECONCILED',
                      severity: short
                          ? LpgStatusSeverity.danger
                          : over
                          ? LpgStatusSeverity.warning
                          : LpgStatusSeverity.success,
                    ),
                  ],
                ),
                const Divider(height: LpgSpacing.xl),
                LpgKeyValueRow(
                  label: 'Expected',
                  value: _money(handover.expectedAmount),
                ),
                const SizedBox(height: LpgSpacing.sm),
                LpgKeyValueRow(
                  label: 'Handed over',
                  value: _money(handover.actualAmount),
                ),
                if (short) ...[
                  const SizedBox(height: LpgSpacing.sm),
                  LpgKeyValueRow(
                    label: 'Shortfall',
                    value: _money(handover.shortfall),
                    emphasize: true,
                    valueColor: colors.statusDanger,
                  ),
                ],
                if (over) ...[
                  const SizedBox(height: LpgSpacing.sm),
                  LpgKeyValueRow(
                    label: 'Over',
                    value: _money(handover.surplus),
                    emphasize: true,
                    valueColor: colors.statusWarning,
                  ),
                ],
                const SizedBox(height: LpgSpacing.md),
                Text(
                  'Declared ${LpgFormat.date(handover.declaredAt)}',
                  style: context.lpgText.bodySmall,
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: LpgSpacing.md),
        const LpgBanner(
          tone: LpgTone.success,
          icon: LpgIcons.successFilled,
          message: "This route's cash has been reconciled.",
        ),
      ],
    );
  }
}
