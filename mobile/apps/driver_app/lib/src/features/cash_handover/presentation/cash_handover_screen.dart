import 'package:api_client/api_client.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../api_provider.dart';
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

    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Confirm cash handover'),
        content: Text(
          'Hand over ₹${amount.toStringAsFixed(2)} for the '
          '${_formatDate(view.routeDate)} route? This cannot be undone.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(dialogContext).pop(true),
            child: const Text('Confirm'),
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;

    setState(() {
      _submitting = true;
      _error = null;
    });

    final result = await ref
        .read(cashHandoverApiProvider)
        .declare(
          routeId: widget.routeId,
          driverId: view.driverId,
          actualAmount: amount,
        );
    if (!mounted) return;

    result.when(
      onSuccess: (_) {
        ref.invalidate(routeCashHandoverProvider(widget.routeId));
        ref.invalidate(pendingCashHandoverProvider);
        ref.invalidate(routeHistoryProvider);
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(const SnackBar(content: Text('Cash handover recorded.')));
        setState(() => _submitting = false);
      },
      onFailure: (failure) {
        final alreadyDone = failure.errorCode == 'CONFLICT';
        if (alreadyDone) {
          ref.invalidate(routeCashHandoverProvider(widget.routeId));
        }
        setState(() {
          _submitting = false;
          _error = alreadyDone
              ? 'This route has already been reconciled.'
              : failure.message;
        });
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    final viewAsync = ref.watch(routeCashHandoverProvider(widget.routeId));

    return Scaffold(
      appBar: AppBar(title: const Text('Cash handover')),
      body: viewAsync.when(
        loading: () => const Center(child: LpgLoadingIndicator()),
        error: (err, _) => LpgEmptyState(
          message: 'Could not load this route.\n$err',
          icon: Icons.error_outline,
          actionLabel: 'Retry',
          onAction: () =>
              ref.invalidate(routeCashHandoverProvider(widget.routeId)),
        ),
        data: (view) {
          if (view.handover != null) {
            return _Receipt(view: view, handover: view.handover!);
          }
          if (view.routeStatus != 'completed') {
            return const LpgEmptyState(
              message:
                  'This route is still in progress. Reconcile the cash once '
                  'every stop is done.',
              icon: Icons.pending_outlined,
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

String _money(double v) => '₹${v.toStringAsFixed(2)}';

String _formatDate(DateTime d) =>
    '${d.year}-${d.month.toString().padLeft(2, '0')}-'
    '${d.day.toString().padLeft(2, '0')}';

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
    final theme = Theme.of(context);
    final colors = theme.extension<LpgColors>()!;
    final stops = view.cashStopCount;

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        if (error != null) ...[
          _ErrorBanner(message: error!),
          const SizedBox(height: 16),
        ],
        LpgCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                '${_formatDate(view.routeDate)} route',
                style: theme.textTheme.labelSmall?.copyWith(
                  color: colors.textSecondary,
                ),
              ),
              const SizedBox(height: 8),
              Text(
                'Expected cash',
                style: theme.textTheme.bodyMedium?.copyWith(
                  color: colors.textSecondary,
                ),
              ),
              const SizedBox(height: 4),
              Text(
                _money(view.expectedAmount),
                style: theme.textTheme.headlineMedium?.copyWith(
                  fontWeight: FontWeight.bold,
                  color: colors.textPrimary,
                ),
              ),
              const SizedBox(height: 4),
              Text(
                'from $stops cash ${stops == 1 ? 'delivery' : 'deliveries'} '
                'on this route',
                style: theme.textTheme.bodySmall?.copyWith(
                  color: colors.textSecondary,
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 24),
        LpgTextField(
          label: 'Amount handed over (₹)',
          controller: amountController,
          keyboardType: const TextInputType.numberWithOptions(decimal: true),
          onChanged: (_) => onAmountChanged(),
        ),
        const SizedBox(height: 8),
        _DeltaLine(expected: view.expectedAmount, entered: entered),
        const SizedBox(height: 32),
        LpgButton(
          label: 'Declare handover',
          icon: Icons.account_balance_wallet_outlined,
          expand: true,
          isLoading: submitting,
          onPressed: submitting ? null : onDeclare,
        ),
        const SizedBox(height: 24),
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
    final colors = Theme.of(context).extension<LpgColors>()!;
    final theme = Theme.of(context);

    if (entered == null) {
      return Text(
        'Count the cash and enter the total.',
        style: theme.textTheme.bodySmall?.copyWith(color: colors.textSecondary),
      );
    }

    final diff = entered! - expected;
    final (String label, Color color) = switch (diff) {
      _ when diff.abs() < 0.005 => (
        'Matches the expected ${_money(expected)}',
        colors.statusSuccess,
      ),
      _ when diff < 0 => ('Short by ${_money(-diff)}', colors.statusDanger),
      _ => ('Over by ${_money(diff)}', colors.statusWarning),
    };

    return Row(
      children: [
        Icon(
          diff.abs() < 0.005 ? Icons.check_circle_outline : Icons.info_outline,
          size: 16,
          color: color,
        ),
        const SizedBox(width: 8),
        Text(label, style: theme.textTheme.bodyMedium?.copyWith(color: color)),
      ],
    );
  }
}

class _Receipt extends StatelessWidget {
  const _Receipt({required this.view, required this.handover});

  final RouteCashHandover view;
  final CashHandover handover;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colors = theme.extension<LpgColors>()!;
    final short = handover.shortfall > 0;
    final over = handover.surplus > 0;

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        LpgCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    handover.handoverNumber ?? 'Cash handover',
                    style: theme.textTheme.titleMedium?.copyWith(
                      fontWeight: FontWeight.bold,
                      color: colors.textPrimary,
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
              const SizedBox(height: 16),
              _AmountRow(label: 'Expected', value: handover.expectedAmount),
              const SizedBox(height: 8),
              _AmountRow(label: 'Handed over', value: handover.actualAmount),
              if (short) ...[
                const SizedBox(height: 8),
                _AmountRow(
                  label: 'Shortfall',
                  value: handover.shortfall,
                  emphasise: colors.statusDanger,
                ),
              ],
              if (over) ...[
                const SizedBox(height: 8),
                _AmountRow(
                  label: 'Over',
                  value: handover.surplus,
                  emphasise: colors.statusWarning,
                ),
              ],
              const SizedBox(height: 16),
              Text(
                'Declared ${_formatDate(handover.declaredAt)}',
                style: theme.textTheme.bodySmall?.copyWith(
                  color: colors.textSecondary,
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 16),
        Text(
          "This route's cash has been reconciled.",
          style: theme.textTheme.bodyMedium?.copyWith(
            color: colors.textSecondary,
          ),
        ),
      ],
    );
  }
}

class _AmountRow extends StatelessWidget {
  const _AmountRow({
    required this.label,
    required this.value,
    this.emphasise,
  });

  final String label;
  final double value;
  final Color? emphasise;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colors = theme.extension<LpgColors>()!;
    final style = theme.textTheme.bodyLarge?.copyWith(
      color: emphasise ?? colors.textPrimary,
      fontWeight: emphasise != null ? FontWeight.bold : FontWeight.normal,
    );
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(label, style: style),
        Text(_money(value), style: style),
      ],
    );
  }
}

class _ErrorBanner extends StatelessWidget {
  const _ErrorBanner({required this.message});

  final String message;

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).extension<LpgColors>()!;
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: colors.statusDanger.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: colors.statusDanger),
      ),
      child: Row(
        children: [
          Icon(Icons.error_outline, color: colors.statusDanger),
          const SizedBox(width: 12),
          Expanded(
            child: Text(message, style: TextStyle(color: colors.statusDanger)),
          ),
        ],
      ),
    );
  }
}
