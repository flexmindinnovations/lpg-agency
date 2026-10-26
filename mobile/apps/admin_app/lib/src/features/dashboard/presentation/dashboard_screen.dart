import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../api_result.dart';
import '../data/dashboard_providers.dart';

class DashboardScreen extends ConsumerWidget {
  const DashboardScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final colors = context.lpgColors;
    final text = context.lpgText;

    final summaryAsync = ref.watch(dashboardSummaryProvider);
    final opsAsync = ref.watch(operationsSnapshotProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Agency Dashboard'),
        actions: [
          IconButton(
            icon: const Icon(LpgIcons.home),
            onPressed: () {
              ref.invalidate(dashboardSummaryProvider);
              ref.invalidate(operationsSnapshotProvider);
            },
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: () async {
          ref.invalidate(dashboardSummaryProvider);
          ref.invalidate(operationsSnapshotProvider);
        },
        child: SingleChildScrollView(
          padding: LpgSpacing.page,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              opsAsync.when(
                loading: () => const LpgSkeleton(height: 120),
                error: (err, _) => LpgErrorState(
                  message: errorMessage(err),
                  onRetry: () => ref.invalidate(operationsSnapshotProvider),
                ),
                data: (ops) => LpgHeroCard(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('Today\'s Bookings', style: text.bodyMedium?.copyWith(color: colors.onHero)),
                      const SizedBox(height: LpgSpacing.xs),
                      Text('${ops.orders.bookingsToday}', style: text.headlineLarge?.copyWith(color: colors.onHero)),
                      const SizedBox(height: LpgSpacing.sm),
                      Text(
                        '${ops.orders.deliveredToday} Delivered  •  ${ops.orders.failedToday} Failed  •  ${ops.orders.pendingCancellations} Pending Cancellation',
                        style: text.bodySmall?.copyWith(color: colors.onHero),
                      ),
                    ],
                  ),
                ),
              ),

              const SizedBox(height: LpgSpacing.lg),
              Text('Agency KPIs & Resources', style: text.titleMedium),
              const SizedBox(height: LpgSpacing.md),

              summaryAsync.when(
                loading: () => const LpgSkeletonList(itemCount: 3),
                error: (err, _) => LpgErrorState(
                  message: errorMessage(err),
                  onRetry: () => ref.invalidate(dashboardSummaryProvider),
                ),
                data: (summary) => Column(
                  children: [
                    Row(
                      children: [
                        Expanded(
                          child: LpgStatTile(
                            label: 'Active Drivers',
                            value: '${summary.driverCount}',
                          ),
                        ),
                        const SizedBox(width: LpgSpacing.md),
                        Expanded(
                          child: LpgStatTile(
                            label: 'Customers',
                            value: '${summary.customerCount}',
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: LpgSpacing.lg),

                    Align(
                      alignment: Alignment.centerLeft,
                      child: Text('Cylinder Catalog & Prices', style: text.titleSmall),
                    ),
                    const SizedBox(height: LpgSpacing.sm),
                    ...summary.priceCards.map((card) => Padding(
                          padding: const EdgeInsets.only(bottom: LpgSpacing.sm),
                          child: LpgCard(
                            child: Row(
                              mainAxisAlignment: MainAxisAlignment.spaceBetween,
                              children: [
                                Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(card.name, style: text.bodyLarge),
                                    Text(
                                      '${card.weightKg} kg  •  ${card.customerType}',
                                      style: text.bodySmall?.copyWith(color: colors.textSecondary),
                                    ),
                                  ],
                                ),
                                Text(
                                  LpgFormat.currency(card.price),
                                  style: text.titleMedium?.copyWith(color: colors.actionPrimary),
                                ),
                              ],
                            ),
                          ),
                        )),

                    const SizedBox(height: LpgSpacing.lg),
                    Align(
                      alignment: Alignment.centerLeft,
                      child: Text('Recent Activity', style: text.titleSmall),
                    ),
                    const SizedBox(height: LpgSpacing.sm),
                    if (summary.recentActivity.isEmpty)
                      const LpgEmptyState(
                        message: 'No recent activity reported today',
                        icon: LpgIcons.home,
                      )
                    else
                      ...summary.recentActivity.take(5).map((act) => Padding(
                            padding: const EdgeInsets.only(bottom: LpgSpacing.xs),
                            child: LpgListTile(
                              title: '${act.actorDisplayName}: ${act.action}',
                              subtitle: '${act.entityName} ${act.entityDisplayName}  •  ${LpgFormat.dateTime(act.performedAt)}',
                            ),
                          )),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
