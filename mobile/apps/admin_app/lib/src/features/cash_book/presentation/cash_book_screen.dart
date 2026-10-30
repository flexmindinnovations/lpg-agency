import 'package:api_client/api_client.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../api_result.dart';
import '../../../shared/metric_tile.dart';
import '../../approvals/data/approvals_provider.dart';
import '../data/cash_book_provider.dart';

/// The agency's cash for one day: what came in and how, what each driver is
/// still carrying, and where the handovers stand. Step back and forward
/// through days, or tap the date to jump.
class CashBookScreen extends ConsumerStatefulWidget {
  const CashBookScreen({super.key});

  @override
  ConsumerState<CashBookScreen> createState() => _CashBookScreenState();
}

class _CashBookScreenState extends ConsumerState<CashBookScreen> {
  late DateTime _day = _today;

  static DateTime get _today {
    final now = DateTime.now();
    return DateTime(now.year, now.month, now.day);
  }

  bool get _isToday => _day == _today;

  void _reload() {
    ref.invalidate(cashBookProvider);
    ref.invalidate(cashInHandProvider);
    ref.invalidate(pendingCashHandoversProvider);
  }

  void _step(int days) {
    final next = _day.add(Duration(days: days));
    if (next.isAfter(_today)) return;
    setState(() => _day = next);
  }

  Future<void> _pick() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _day,
      firstDate: DateTime(2020),
      lastDate: _today,
    );
    if (picked != null) {
      setState(() => _day = DateTime(picked.year, picked.month, picked.day));
    }
  }

  @override
  Widget build(BuildContext context) {
    final book = ref.watch(cashBookProvider(cashBookDay(_day)));
    final held = ref.watch(cashInHandProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Cash book'),
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
          await ref.read(cashBookProvider(cashBookDay(_day)).future);
        },
        child: ListView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: LpgSpacing.page,
          children: [
            _DayPicker(
              day: _day,
              isToday: _isToday,
              onPrevious: () => _step(-1),
              onNext: _isToday ? null : () => _step(1),
              onPick: _pick,
            ),
            const SizedBox(height: LpgSpacing.md),
            book.when(
              loading: () => const LpgSkeletonList(itemCount: 3),
              error: (err, _) =>
                  LpgErrorState(message: errorMessage(err), onRetry: _reload),
              data: (b) => _DayBody(book: b, isToday: _isToday),
            ),
            const SectionHeading('With the drivers now', topGap: LpgSpacing.lg),
            held.when(
              loading: () => const LpgSkeleton(height: 96),
              error: (err, _) => Text(
                errorMessage(err),
                style: context.lpgText.bodyMedium?.copyWith(
                  color: context.lpgColors.statusDanger,
                ),
              ),
              data: (h) => _CashInHand(held: h),
            ),
            const SizedBox(height: LpgSpacing.xl),
          ],
        ),
      ),
    );
  }
}

class _DayPicker extends StatelessWidget {
  const _DayPicker({
    required this.day,
    required this.isToday,
    required this.onPrevious,
    required this.onNext,
    required this.onPick,
  });

  final DateTime day;
  final bool isToday;
  final VoidCallback onPrevious;
  final VoidCallback? onNext;
  final VoidCallback onPick;

  @override
  Widget build(BuildContext context) {
    final text = context.lpgText;
    final colors = context.lpgColors;

    return LpgCard(
      padding: const EdgeInsets.symmetric(
        horizontal: LpgSpacing.xs,
        vertical: LpgSpacing.xs,
      ),
      child: Row(
        children: [
          IconButton(
            tooltip: 'Previous day',
            icon: const Icon(LpgIcons.back),
            onPressed: onPrevious,
          ),
          Expanded(
            child: InkWell(
              borderRadius: BorderRadius.circular(LpgRadius.md),
              onTap: onPick,
              child: Padding(
                padding: const EdgeInsets.symmetric(vertical: LpgSpacing.sm),
                child: Column(
                  children: [
                    Text(
                      isToday ? 'Today' : LpgFormat.date(day),
                      style: text.titleMedium,
                    ),
                    Text(
                      isToday ? LpgFormat.date(day) : 'Tap to change the day',
                      style: text.bodySmall?.copyWith(
                        color: colors.textSecondary,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
          IconButton(
            tooltip: 'Next day',
            icon: const Icon(LpgIcons.chevronRight),
            onPressed: onNext,
          ),
        ],
      ),
    );
  }
}

class _DayBody extends StatelessWidget {
  const _DayBody({required this.book, required this.isToday});

  final CashBook book;
  final bool isToday;

  String _method(String method) => switch (method) {
    'cash' => 'Cash',
    'upi' => 'UPI',
    'card' => 'Card',
    'cheque' => 'Cheque',
    'bank_transfer' => 'Bank transfer',
    'online' => 'Online',
    _ => LpgFormat.sentence(method),
  };

  String _paymentsLabel(List<CashBookCollection> collections) {
    final count = collections.fold<int>(0, (n, c) => n + c.paymentCount);
    if (count == 0) return 'No payments recorded';
    return '$count ${count == 1 ? 'payment' : 'payments'}';
  }

  @override
  Widget build(BuildContext context) {
    final text = context.lpgText;
    final colors = context.lpgColors;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        LpgHeroCard(
          watermark: LpgIcons.wallet,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                isToday ? 'Collected today' : 'Collected on this day',
                style: text.bodyMedium?.copyWith(color: colors.onHero),
              ),
              const SizedBox(height: LpgSpacing.xs),
              Text(
                LpgFormat.currency(book.totalCollected),
                style: text.headlineLarge?.copyWith(color: colors.onHero),
              ),
              const SizedBox(height: LpgSpacing.xs),
              Text(
                _paymentsLabel(book.collections),
                style: text.bodySmall?.copyWith(color: colors.onHero),
              ),
            ],
          ),
        ),
        const SectionHeading('How it came in', topGap: LpgSpacing.lg),
        if (book.collections.isEmpty)
          Text(
            'No payments were recorded on this day.',
            style: text.bodyMedium?.copyWith(color: colors.textSecondary),
          )
        else
          LpgGroupedList(
            children: [
              for (final c in book.collections)
                LpgListTile(
                  leadingIcon: c.method == 'cash'
                      ? LpgIcons.cash
                      : LpgIcons.payment,
                  title: _method(c.method),
                  subtitle:
                      '${c.paymentCount} ${c.paymentCount == 1 ? 'payment' : 'payments'}',
                  trailing: Text(
                    LpgFormat.currency(c.amount),
                    style: text.titleSmall,
                  ),
                ),
            ],
          ),
        const SectionHeading('Driver cash handed over', topGap: LpgSpacing.lg),
        MetricGrid(
          tiles: [
            MetricTile(
              label: 'Expected',
              value: LpgFormat.currency(book.expectedTotal),
              caption:
                  '${book.handoverCount} ${book.handoverCount == 1 ? 'handover' : 'handovers'}',
              icon: LpgIcons.handover,
            ),
            MetricTile(
              label: 'Handed over',
              value: LpgFormat.currency(book.handedOverTotal),
              icon: LpgIcons.cash,
              tone: LpgTone.success,
            ),
            MetricTile(
              label: 'Short',
              value: LpgFormat.currency(book.shortfallTotal),
              icon: LpgIcons.warning,
              tone: LpgTone.danger,
              attention: book.shortfallTotal > 0,
            ),
            MetricTile(
              label: 'Excess',
              value: LpgFormat.currency(book.excessTotal),
              icon: LpgIcons.trendUp,
              tone: LpgTone.info,
            ),
          ],
        ),
        const SectionHeading('Checked by the office'),
        LpgGroupedList(
          children: [
            LpgListTile(
              leadingIcon: LpgIcons.verified,
              leadingTone: LpgTone.success,
              title: 'Accepted',
              trailing: Text(
                LpgFormat.currency(book.acceptedTotal),
                style: text.titleSmall,
              ),
            ),
            LpgListTile(
              leadingIcon: LpgIcons.blocked,
              leadingTone: LpgTone.danger,
              title: 'Disputed',
              trailing: Text(
                LpgFormat.currency(book.disputedTotal),
                style: text.titleSmall,
              ),
            ),
            LpgListTile(
              leadingIcon: LpgIcons.pending,
              leadingTone: LpgTone.warning,
              title: 'Still to check',
              subtitle: book.pendingCount > 0
                  ? '${book.pendingCount} waiting for you'
                  : null,
              trailing: Text(
                LpgFormat.currency(book.pendingTotal),
                style: text.titleSmall,
              ),
              showChevron: true,
              onTap: () => context.pushNamed('approvals'),
            ),
          ],
        ),
      ],
    );
  }
}

class _CashInHand extends StatelessWidget {
  const _CashInHand({required this.held});

  final CashInHand held;

  @override
  Widget build(BuildContext context) {
    final text = context.lpgText;
    final colors = context.lpgColors;

    if (held.drivers.isEmpty) {
      return LpgCard(
        variant: LpgCardVariant.tonal,
        tone: LpgTone.success,
        child: Row(
          children: [
            const LpgIconBox(icon: LpgIcons.allDone, tone: LpgTone.success),
            const SizedBox(width: LpgSpacing.md),
            Expanded(
              child: Text('No driver is carrying cash.', style: text.bodyLarge),
            ),
          ],
        ),
      );
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        LpgCard(
          child: Row(
            children: [
              const LpgIconBox(icon: LpgIcons.cash, tone: LpgTone.accent),
              const SizedBox(width: LpgSpacing.md),
              Expanded(
                child: Text('Total cash with drivers', style: text.bodyLarge),
              ),
              Text(LpgFormat.currency(held.totalCash), style: text.titleMedium),
            ],
          ),
        ),
        const SizedBox(height: LpgSpacing.sm),
        LpgGroupedList(
          children: [
            for (final d in held.drivers)
              LpgListTile(
                leading: LpgAvatar(name: d.driverName),
                title: d.driverName,
                subtitle:
                    '${d.stopCount} ${d.stopCount == 1 ? 'stop' : 'stops'}'
                    ' · since ${LpgFormat.shortDate(d.oldestRouteDate)}',
                trailing: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    Text(
                      LpgFormat.currency(d.cashAmount),
                      style: text.titleSmall,
                    ),
                    if (d.upiAmount > 0)
                      Text(
                        '${LpgFormat.currency(d.upiAmount)} UPI',
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
