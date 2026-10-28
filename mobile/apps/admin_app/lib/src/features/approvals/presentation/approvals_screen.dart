import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../api_result.dart';
import '../data/approvals_provider.dart';
import 'cash_handover_review_screen.dart';

class ApprovalsScreen extends ConsumerStatefulWidget {
  const ApprovalsScreen({super.key});

  @override
  ConsumerState<ApprovalsScreen> createState() => _ApprovalsScreenState();
}

class _ApprovalsScreenState extends ConsumerState<ApprovalsScreen> {
  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;
    final text = context.lpgText;

    final handoversAsync = ref.watch(pendingCashHandoversProvider);

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
      body: RefreshIndicator(
        onRefresh: () async {
          ref.invalidate(pendingCashHandoversProvider);
        },
        child: SingleChildScrollView(
          padding: LpgSpacing.page,
          physics: const AlwaysScrollableScrollPhysics(),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text('Cash Handover Reviews', style: text.titleMedium),
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

                  return ListView.separated(
                    shrinkWrap: true,
                    physics: const NeverScrollableScrollPhysics(),
                    itemCount: handovers.length,
                    separatorBuilder: (_, _) =>
                        const SizedBox(height: LpgSpacing.sm),
                    itemBuilder: (context, index) {
                      final item = handovers[index];
                      return LpgCard(
                        onTap: () {
                          Navigator.push(
                            context,
                            MaterialPageRoute(
                              builder: (_) => CashHandoverReviewScreen(
                                cashHandoverId: item.id,
                                driverName: item.driverName,
                                expectedAmount: item.expectedAmount,
                                actualAmount: item.actualAmount,
                                shortfall: item.shortfall,
                                denominations: item.denominations,
                                varianceReason: item.varianceReason,
                                upiExpected: item.upiExpected,
                              ),
                            ),
                          );
                        },
                        child: Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(item.driverName, style: text.titleMedium),
                                const SizedBox(height: LpgSpacing.xs),
                                Text(
                                  'Route #${item.routeId.substring(0, 8)}  •  ${LpgFormat.date(item.routeDate)}',
                                  style: text.bodySmall?.copyWith(
                                    color: colors.textSecondary,
                                  ),
                                ),
                              ],
                            ),
                            Column(
                              crossAxisAlignment: CrossAxisAlignment.end,
                              children: [
                                Text(
                                  LpgFormat.currency(item.actualAmount),
                                  style: text.titleSmall?.copyWith(
                                    color: colors.actionPrimary,
                                  ),
                                ),
                                if (item.shortfall > 0) ...[
                                  const SizedBox(height: LpgSpacing.xs),
                                  const LpgStatusBadge(
                                    label: 'Shortfall',
                                    severity: LpgStatusSeverity.danger,
                                  ),
                                ],
                              ],
                            ),
                          ],
                        ),
                      );
                    },
                  );
                },
              ),
            ],
          ),
        ),
      ),
    );
  }
}
