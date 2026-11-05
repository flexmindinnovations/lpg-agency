import 'package:api_client/api_client.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../cash_handover/data/cash_handover_provider.dart';
import '../../profile/data/profile_provider.dart';
import '../../van_load/data/van_load_provider.dart';
import '../data/active_route_provider.dart';
import 'widgets/location_sharing_card.dart';

/// The Driver App's home tab: today's route at a glance with responsive 10"+ tablet layout.
class TodayScreen extends ConsumerWidget {
  const TodayScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final routeAsync = ref.watch(activeRouteProvider);
    final isExpandedTablet = LpgBreakpoints.isExpanded(context);

    return Scaffold(
      appBar: AppBar(title: const Text('Today')),
      body: RefreshIndicator(
        onRefresh: () {
          ref.invalidate(routeHistoryProvider);
          ref.invalidate(pendingCashHandoversProvider);
          ref.invalidate(myCashInHandProvider);
          ref.invalidate(pendingLoadProvider);
          return ref.refresh(activeRouteProvider.future);
        },
        child: routeAsync.when(
          loading: () => const LpgSkeletonList(itemCount: 4),
          error: (err, _) => ListView(
            padding: LpgSpacing.page,
            children: [
              LpgErrorState(
                message: 'Could not load your route.\n$err',
                onRetry: () => ref.invalidate(activeRouteProvider),
              ),
            ],
          ),
          data: (route) {
            final pendingCash =
                ref.watch(pendingCashHandoversProvider).value ?? const [];
            final pendingLoad = ref.watch(pendingLoadProvider).value;

            if (route == null && pendingCash.isEmpty && pendingLoad == null) {
              return ListView(
                padding: LpgSpacing.page,
                children: const [
                  Padding(
                    padding: EdgeInsets.only(top: LpgSpacing.xxl),
                    child: LpgEmptyState(
                      title: 'Nothing on the road yet',
                      message: 'No route assigned yet.',
                      icon: LpgIcons.truck,
                    ),
                  ),
                ],
              );
            }

            if (isExpandedTablet) {
              return SingleChildScrollView(
                physics: const AlwaysScrollableScrollPhysics(),
                padding: LpgSpacing.page,
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // Left Column (Route Hero & Next Stop)
                    Expanded(
                      flex: 6,
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          if (route != null) ...[
                            _RouteHero(route: route),
                            const SizedBox(height: LpgSpacing.md),
                            _RouteStats(route: route),
                            const SizedBox(height: LpgSpacing.md),
                            const LpgSectionHeader(title: 'Up next'),
                            _NextStopCard(route: route),
                            const SizedBox(height: LpgSpacing.md),
                            const LpgSectionHeader(title: 'Live location'),
                            LocationSharingCard(route: route),
                          ],
                        ],
                      ),
                    ),

                    const SizedBox(width: LpgSpacing.xl),

                    // Right Column (Cash & Inventory Tasks)
                    Expanded(
                      flex: 5,
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const _CashInHandCard(),
                          const SizedBox(height: LpgSpacing.md),
                          if (pendingLoad != null) ...[
                            _PendingLoadCard(route: pendingLoad),
                            const SizedBox(height: LpgSpacing.md),
                          ],
                          for (final view in pendingCash) ...[
                            _PendingCashCard(view: view),
                            const SizedBox(height: LpgSpacing.md),
                          ],
                        ],
                      ),
                    ),
                  ],
                ),
              );
            }

            final sections = <Widget>[
              const _CashInHandCard(),
              if (pendingLoad != null) _PendingLoadCard(route: pendingLoad),
              for (final view in pendingCash) _PendingCashCard(view: view),
              if (route != null) ...[
                _RouteHero(route: route),
                _RouteStats(route: route),
                const LpgSectionHeader(title: 'Up next'),
                _NextStopCard(route: route),
                const LpgSectionHeader(title: 'Live location'),
                LocationSharingCard(route: route),
              ],
            ];

            return ListView(
              padding: LpgSpacing.page,
              children: [
                for (var i = 0; i < sections.length; i++) ...[
                  if (i > 0) const SizedBox(height: LpgSpacing.md),
                  LpgFadeSlideIn(index: i, child: sections[i]),
                ],
              ],
            );
          },
        ),
      ),
    );
  }
}

LpgStatusSeverity _routeSeverity(String status) => switch (status) {
  'in_progress' => LpgStatusSeverity.warning,
  'completed' || 'reconciled' => LpgStatusSeverity.success,
  'cancelled' => LpgStatusSeverity.danger,
  _ => LpgStatusSeverity.info,
};

class _RouteHero extends ConsumerWidget {
  const _RouteHero({required this.route});

  final RouteSummary route;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final vehicle = ref.watch(driverProfileProvider).value?.vehicle;
    final subtitle = [
      if (route.date case final date?) LpgFormat.date(date),
      if (vehicle != null) vehicle.registrationNumber,
    ].join(' · ');
    final colors = context.lpgColors;
    final text = context.lpgText;
    final total = route.stops.length;
    final delivered = route.stops.where((s) => s.status == 'delivered').length;
    final progress = total == 0 ? 0.0 : delivered / total;

    return LpgHeroCard(
      watermark: LpgIcons.route,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  "Today's route",
                  style: text.titleSmall?.copyWith(
                    color: colors.onHero.withValues(alpha: 0.85),
                  ),
                ),
              ),
              LpgStatusBadge(
                label: LpgFormat.statusLabel(route.status),
                severity: _routeSeverity(route.status),
                isLive: route.status == 'in_progress',
              ),
            ],
          ),
          if (subtitle.isNotEmpty) ...[
            const SizedBox(height: LpgSpacing.xs),
            Text(
              subtitle,
              style: text.bodySmall?.copyWith(
                color: colors.onHero.withValues(alpha: 0.85),
              ),
            ),
          ],
          const SizedBox(height: LpgSpacing.md),
          Text(
            '$delivered of $total delivered',
            style: text.headlineSmall?.copyWith(color: colors.onHero),
          ),
          const SizedBox(height: LpgSpacing.smd),
          ClipRRect(
            borderRadius: BorderRadius.circular(LpgRadius.full),
            child: TweenAnimationBuilder<double>(
              tween: Tween(begin: 0, end: progress),
              duration: LpgMotion.large(context),
              curve: LpgMotion.effectsCurve,
              builder: (context, value, _) => LinearProgressIndicator(
                value: value,
                minHeight: LpgSpacing.sm,
                backgroundColor: colors.onHero.withValues(alpha: 0.24),
                valueColor: AlwaysStoppedAnimation<Color>(colors.onHero),
                semanticsLabel: 'Route progress',
                semanticsValue: '${(progress * 100).round()}%',
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _RouteStats extends StatelessWidget {
  const _RouteStats({required this.route});

  final RouteSummary route;

  @override
  Widget build(BuildContext context) {
    final delivered = route.stops.where((s) => s.status == 'delivered').length;
    final failed = route.stops.where((s) => s.status == 'failed').length;
    final remaining = route.stops.length - delivered - failed;

    return IntrinsicHeight(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Expanded(
            child: LpgStatTile(
              label: 'Delivered',
              value: '$delivered',
              icon: LpgIcons.success,
              tone: LpgTone.success,
            ),
          ),
          const SizedBox(width: LpgSpacing.smd),
          Expanded(
            child: LpgStatTile(
              label: 'Remaining',
              value: '$remaining',
              icon: LpgIcons.location,
              tone: LpgTone.primary,
            ),
          ),
          const SizedBox(width: LpgSpacing.smd),
          Expanded(
            child: LpgStatTile(
              label: 'Failed',
              value: '$failed',
              icon: LpgIcons.cancel,
              tone: failed > 0 ? LpgTone.danger : LpgTone.neutral,
            ),
          ),
        ],
      ),
    );
  }
}

class _NextStopCard extends StatelessWidget {
  const _NextStopCard({required this.route});

  final RouteSummary route;

  @override
  Widget build(BuildContext context) {
    RouteStopSummary? pending;
    for (final s in route.stops) {
      if (s.status != 'delivered' && s.status != 'failed') {
        pending = s;
        break;
      }
    }
    final next = pending;

    if (next == null) {
      return const LpgCard(
        variant: LpgCardVariant.tonal,
        tone: LpgTone.success,
        padding: EdgeInsets.zero,
        child: LpgListTile(
          leadingIcon: LpgIcons.allDone,
          leadingTone: LpgTone.success,
          title: 'All stops done for this route.',
        ),
      );
    }

    return LpgCard(
      padding: EdgeInsets.zero,
      onTap: () =>
          context.goNamed('stop', pathParameters: {'orderId': next.orderId}),
      child: LpgListTile(
        leadingIcon: LpgIcons.navigate,
        title: 'Next stop · Stop ${next.sequenceNumber}',
        subtitle:
            'Order ${LpgFormat.orderNumber(next.orderNumber, next.orderId)}',
        showChevron: true,
      ),
    );
  }
}

class _PendingLoadCard extends StatelessWidget {
  const _PendingLoadCard({required this.route});

  final RouteSummary route;

  @override
  Widget build(BuildContext context) {
    final total = route.loadedLines.fold<int>(0, (s, l) => s + l.quantity);

    return LpgCard(
      variant: LpgCardVariant.tonal,
      tone: LpgTone.info,
      padding: EdgeInsets.zero,
      onTap: () =>
          context.pushNamed('vanLoad', pathParameters: {'routeId': route.id}),
      child: LpgListTile(
        leadingIcon: LpgIcons.inventory,
        leadingTone: LpgTone.info,
        title: 'Check your van load',
        subtitle: total == 0
            ? "Review today's route manifest"
            : "$total cylinder${total == 1 ? '' : 's'} for today's route",
        showChevron: true,
      ),
    );
  }
}

class _PendingCashCard extends StatelessWidget {
  const _PendingCashCard({required this.view});

  final RouteCashHandover view;

  @override
  Widget build(BuildContext context) {
    return LpgCard(
      variant: LpgCardVariant.tonal,
      tone: LpgTone.warning,
      padding: EdgeInsets.zero,
      onTap: () => context.pushNamed(
        'cashHandover',
        pathParameters: {'routeId': view.routeId},
      ),
      child: LpgListTile(
        leadingIcon: LpgIcons.handover,
        leadingTone: LpgTone.warning,
        title: 'Cash reconciliation pending',
        subtitle:
            'Declare ${LpgFormat.currency(view.expectedAmount)} from your '
            '${LpgFormat.date(view.routeDate)} route',
        showChevron: true,
      ),
    );
  }
}

class _CashInHandCard extends ConsumerWidget {
  const _CashInHandCard();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final held = ref.watch(myCashInHandProvider).value;
    if (held == null || (held.cashAmount <= 0 && held.upiAmount <= 0)) {
      return const SizedBox.shrink();
    }
    return LpgCard(
      variant: LpgCardVariant.tonal,
      tone: LpgTone.info,
      padding: EdgeInsets.zero,
      child: LpgListTile(
        leadingIcon: LpgIcons.cash,
        leadingTone: LpgTone.info,
        title: 'Cash in hand ${LpgFormat.currency(held.cashAmount)}',
        subtitle: held.upiAmount > 0
            ? '${LpgFormat.currency(held.upiAmount)} was paid by UPI, so you '
                  'do not hand that over'
            : 'Collected since your last handover',
      ),
    );
  }
}
