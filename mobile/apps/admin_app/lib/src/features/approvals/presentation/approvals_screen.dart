import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:api_client/api_client.dart';

import '../../../api_result.dart';
import '../../../i18n/admin_strings.dart';
import '../data/approvals_provider.dart';
import 'cash_handover_review_screen.dart';

class ApprovalsScreen extends ConsumerStatefulWidget {
  const ApprovalsScreen({super.key});

  @override
  ConsumerState<ApprovalsScreen> createState() => _ApprovalsScreenState();
}

class _ApprovalsScreenState extends ConsumerState<ApprovalsScreen> {
  /// The handover open in the right-hand pane on a tablet.
  String? _selectedId;

  @override
  Widget build(BuildContext context) {
    final twoPane = LpgBreakpoints.isExpanded(context);
    final text = context.lpgText;

    final handoversAsync = ref.watch(pendingCashHandoversProvider);

    final list = RefreshIndicator(
      onRefresh: () async {
        ref.invalidate(pendingCashHandoversProvider);
      },
      child: SingleChildScrollView(
        padding: LpgSpacing.page,
        physics: const AlwaysScrollableScrollPhysics(),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            LpgSectionHeader.compact(title: 'Cash handover reviews'),
            const SizedBox(height: LpgSpacing.sm),

            handoversAsync.when(
              loading: () => const LpgSkeletonList(itemCount: 3),
              error: (err, _) => LpgErrorState(
                message: errorMessage(err),
                onRetry: () => ref.invalidate(pendingCashHandoversProvider),
              ),
              data: (handovers) {
                if (handovers.isEmpty) {
                  return const LpgEmptyState(
                    message: 'No driver cash handovers pending review.',
                    icon: LpgIcons.support,
                  );
                }

                return LpgGroupedList(
                  children: [
                    for (final item in handovers)
                      LpgListTile(
                        leadingIcon: LpgIcons.cash,
                        leadingTone: item.shortfall > 0
                            ? LpgTone.danger
                            : LpgTone.accent,
                        title: item.driverName,
                        subtitle:
                            'Route #${item.routeId.substring(0, 8)}  •  '
                            '${LpgFormat.date(item.routeDate)}',
                        trailing: Column(
                          mainAxisSize: MainAxisSize.min,
                          crossAxisAlignment: CrossAxisAlignment.end,
                          children: [
                            Text(
                              LpgFormat.currency(item.actualAmount),
                              style: text.titleSmall,
                            ),
                            if (item.shortfall > 0)
                              const LpgStatusBadge(
                                label: 'Shortfall',
                                severity: LpgStatusSeverity.danger,
                              ),
                          ],
                        ),
                        showChevron: true,
                        onTap: () {
                          if (twoPane) {
                            setState(() => _selectedId = item.id);
                            return;
                          }
                          Navigator.push(
                            context,
                            MaterialPageRoute(
                              builder: (_) => _review(item, embedded: false),
                            ),
                          );
                        },
                      ),
                  ],
                );
              },
            ),
          ],
        ),
      ),
    );

    final selected = handoversAsync.value
        ?.where((h) => h.id == _selectedId)
        .firstOrNull;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Pending Approvals'),
        actions: [
          IconButton(
            icon: const Icon(LpgIcons.support),
            onPressed: () => ref.invalidate(pendingCashHandoversProvider),
          ),
        ],
      ),
      body: twoPane
          ? Row(
              children: [
                SizedBox(width: 420, child: list),
                VerticalDivider(
                  width: 1,
                  color: context.lpgColors.borderDefault,
                ),
                Expanded(
                  child: selected == null
                      ? LpgEmptyState(
                          message: context.strings.nav.selectHandover,
                          icon: LpgIcons.cash,
                        )
                      : _review(selected, embedded: true),
                ),
              ],
            )
          : list,
    );
  }

  Widget _review(
    CashHandoverRegisterEntryResponse item, {
    required bool embedded,
  }) => CashHandoverReviewScreen(
    key: ValueKey(item.id),
    cashHandoverId: item.id,
    driverName: item.driverName,
    expectedAmount: item.expectedAmount,
    actualAmount: item.actualAmount,
    shortfall: item.shortfall,
    denominations: item.denominations,
    varianceReason: item.varianceReason,
    upiExpected: item.upiExpected,
    collections: item.collections,
    embedded: embedded,
    onDone: embedded ? () => setState(() => _selectedId = null) : null,
  );
}
