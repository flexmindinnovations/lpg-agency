import 'package:api_client/api_client.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../cash_handover/data/cash_handover_provider.dart';
import '../data/active_route_provider.dart';
import 'widgets/location_sharing_card.dart';

/// The Driver App's home tab: today's route at a glance — status, progress,
/// the next stop to hit, and the live-location-sharing switch.
class TodayScreen extends ConsumerWidget {
  const TodayScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final routeAsync = ref.watch(activeRouteProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Today')),
      body: RefreshIndicator(
        onRefresh: () => ref.refresh(activeRouteProvider.future),
        child: routeAsync.when(
          loading: () => const Center(child: LpgLoadingIndicator()),
          error: (err, _) => ListView(
            children: [
              LpgEmptyState(
                message: 'Could not load your route.\n$err',
                icon: Icons.error_outline,
                actionLabel: 'Retry',
                onAction: () => ref.invalidate(activeRouteProvider),
              ),
            ],
          ),
          data: (route) {
            final pendingCash = ref.watch(pendingCashHandoverProvider).value;
            return ListView(
              padding: const EdgeInsets.all(16),
              children: [
                if (pendingCash != null) ...[
                  _PendingCashCard(view: pendingCash),
                  const SizedBox(height: 16),
                ],
                if (route == null)
                  const Padding(
                    padding: EdgeInsets.only(top: 80),
                    child: LpgEmptyState(
                      message: 'No route assigned yet.',
                      icon: Icons.local_shipping_outlined,
                    ),
                  )
                else ...[
                  _RouteStatusCard(route: route),
                  const SizedBox(height: 16),
                  _NextStopCard(route: route),
                  const SizedBox(height: 16),
                  LocationSharingCard(route: route),
                ],
              ],
            );
          },
        ),
      ),
    );
  }
}

class _RouteStatusCard extends StatelessWidget {
  const _RouteStatusCard({required this.route});

  final RouteSummary route;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colors = theme.extension<LpgColors>()!;
    final total = route.stops.length;
    final delivered = route.stops.where((s) => s.status == 'delivered').length;

    return LpgCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                'Route',
                style: theme.textTheme.labelSmall?.copyWith(
                  color: colors.textSecondary,
                ),
              ),
              LpgStatusBadge(
                label: route.status.replaceAll('_', ' ').toUpperCase(),
                severity: switch (route.status) {
                  'in_progress' => LpgStatusSeverity.warning,
                  'completed' || 'reconciled' => LpgStatusSeverity.success,
                  'cancelled' => LpgStatusSeverity.danger,
                  _ => LpgStatusSeverity.info,
                },
              ),
            ],
          ),
          const SizedBox(height: 12),
          Text(
            '$delivered of $total delivered',
            style: theme.textTheme.titleLarge?.copyWith(
              fontWeight: FontWeight.bold,
              color: colors.textPrimary,
            ),
          ),
          const SizedBox(height: 8),
          ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: LinearProgressIndicator(
              value: total == 0 ? 0 : delivered / total,
              minHeight: 6,
              backgroundColor: colors.borderDefault,
              valueColor: AlwaysStoppedAnimation<Color>(colors.actionPrimary),
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
    final theme = Theme.of(context);
    final colors = theme.extension<LpgColors>()!;

    RouteStopSummary? pending;
    for (final s in route.stops) {
      if (s.status != 'delivered' && s.status != 'failed') {
        pending = s;
        break;
      }
    }
    final next = pending;

    if (next == null) {
      return LpgCard(
        child: Row(
          children: [
            Icon(Icons.done_all, color: colors.statusSuccess),
            const SizedBox(width: 12),
            Text(
              'All stops done for this route.',
              style: theme.textTheme.bodyMedium?.copyWith(
                color: colors.textPrimary,
              ),
            ),
          ],
        ),
      );
    }

    return LpgCard(
      padding: EdgeInsets.zero,
      onTap: () =>
          context.goNamed('stop', pathParameters: {'orderId': next.orderId}),
      child: LpgListTile(
        leadingIcon: Icons.navigation_outlined,
        title: 'Next stop · Stop ${next.sequenceNumber}',
        subtitle: 'Order ${next.orderId.substring(0, 8).toUpperCase()}',
        trailing: Icon(Icons.chevron_right, color: colors.textSecondary),
      ),
    );
  }
}

/// Nudge shown once a route finishes and its cash still needs declaring —
/// the route is gone from `activeRouteProvider` by then, so this is the
/// driver's way back to it.
class _PendingCashCard extends StatelessWidget {
  const _PendingCashCard({required this.view});

  final RouteCashHandover view;

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).extension<LpgColors>()!;
    final d = view.routeDate;
    final date =
        '${d.year}-${d.month.toString().padLeft(2, '0')}-'
        '${d.day.toString().padLeft(2, '0')}';

    return LpgCard(
      padding: EdgeInsets.zero,
      onTap: () => context.goNamed(
        'cashHandover',
        pathParameters: {'routeId': view.routeId},
      ),
      child: LpgListTile(
        leadingIcon: Icons.account_balance_wallet_outlined,
        title: 'Cash reconciliation pending',
        subtitle:
            'Declare ₹${view.expectedAmount.toStringAsFixed(2)} from your '
            '$date route',
        trailing: Icon(Icons.chevron_right, color: colors.textSecondary),
      ),
    );
  }
}
