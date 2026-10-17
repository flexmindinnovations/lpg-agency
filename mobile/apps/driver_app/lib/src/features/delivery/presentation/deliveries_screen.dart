import 'package:api_client/api_client.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../cash_handover/data/cash_handover_provider.dart';
import '../data/active_route_provider.dart';
import 'widgets/stop_tile.dart';

/// The Deliveries tab: the current route's stops (→ Stop Detail → depart /
/// Record Delivery) plus a "Past routes" history section.
class DeliveriesScreen extends ConsumerWidget {
  const DeliveriesScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final routeAsync = ref.watch(activeRouteProvider);
    final historyAsync = ref.watch(routeHistoryProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Deliveries')),
      body: RefreshIndicator(
        onRefresh: () async {
          ref.invalidate(activeRouteProvider);
          ref.invalidate(routeHistoryProvider);
          await ref.read(activeRouteProvider.future);
        },
        child: ListView(
          padding: LpgSpacing.page,
          children: [
            LpgSectionHeader(
              title: 'Current route',
              subtitle: routeAsync.value == null
                  ? null
                  : _progressLabel(routeAsync.value!),
            ),
            routeAsync.when(
              loading: () => const _SectionSkeleton(),
              error: (err, _) => LpgErrorState(
                message: 'Could not load your route.\n$err',
                onRetry: () => ref.invalidate(activeRouteProvider),
              ),
              data: (route) {
                if (route == null) {
                  return const _MutedNote(
                    'No active route right now.',
                    icon: LpgIcons.truck,
                  );
                }
                return Column(
                  children: [
                    for (final (i, stop) in route.stops.indexed)
                      LpgFadeSlideIn(
                        index: i,
                        child: Padding(
                          padding: const EdgeInsets.only(
                            bottom: LpgSpacing.smd,
                          ),
                          child: StopTile(
                            stop: stop,
                            onTap: () => context.goNamed(
                              'stop',
                              pathParameters: {'orderId': stop.orderId},
                            ),
                          ),
                        ),
                      ),
                  ],
                );
              },
            ),
            const SizedBox(height: LpgSpacing.md),
            const LpgSectionHeader(title: 'Past routes'),
            historyAsync.when(
              loading: () => const _SectionSkeleton(),
              error: (err, _) => const _MutedNote(
                'Could not load history.',
                icon: LpgIcons.error,
              ),
              data: (routes) {
                if (routes.isEmpty) {
                  return const _MutedNote(
                    'No finished routes yet.',
                    icon: LpgIcons.history,
                  );
                }
                final pendingCashRouteId = ref
                    .watch(pendingCashHandoverProvider)
                    .value
                    ?.routeId;
                return Column(
                  children: [
                    for (final (i, r) in routes.indexed)
                      LpgFadeSlideIn(
                        index: i,
                        child: Padding(
                          padding: const EdgeInsets.only(
                            bottom: LpgSpacing.smd,
                          ),
                          child: _HistoryRow(
                            route: r,
                            cashPending: r.id == pendingCashRouteId,
                            onTap: r.status == 'completed'
                                ? () => context.goNamed(
                                    'cashHandover',
                                    pathParameters: {'routeId': r.id},
                                  )
                                : null,
                          ),
                        ),
                      ),
                  ],
                );
              },
            ),
          ],
        ),
      ),
    );
  }

  static String _progressLabel(RouteSummary route) {
    final done = route.stops
        .where((s) => s.status == 'delivered' || s.status == 'failed')
        .length;
    return '$done of ${route.stops.length} completed';
  }
}

/// A short shimmer placeholder for one section while it loads — the screen
/// keeps its two-section shape instead of collapsing to a spinner.
class _SectionSkeleton extends StatelessWidget {
  const _SectionSkeleton();

  @override
  Widget build(BuildContext context) =>
      const LpgSkeletonList(itemCount: 2, padding: EdgeInsets.zero);
}

class _HistoryRow extends StatelessWidget {
  const _HistoryRow({
    required this.route,
    this.cashPending = false,
    this.onTap,
  });

  final RouteSummary route;
  final bool cashPending;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;
    final date = route.date;
    final dateLabel = date == null ? 'Route' : LpgFormat.date(date);
    final n = route.stops.length;
    final cancelled = route.status == 'cancelled';
    return LpgCard(
      padding: EdgeInsets.zero,
      onTap: onTap,
      child: LpgListTile(
        leadingIcon: LpgIcons.history,
        leadingTone: LpgTone.neutral,
        title: dateLabel,
        subtitle:
            '$n stop${n == 1 ? '' : 's'} · '
            '${LpgFormat.sentence(route.status)}',
        trailing: cashPending
            ? const LpgStatusBadge(
                label: 'CASH PENDING',
                severity: LpgStatusSeverity.warning,
              )
            : Icon(
                cancelled ? LpgIcons.cancel : LpgIcons.success,
                size: LpgSizes.iconMd,
                color: cancelled ? colors.statusDanger : colors.statusSuccess,
              ),
        showChevron: onTap != null,
      ),
    );
  }
}

class _MutedNote extends StatelessWidget {
  const _MutedNote(this.text, {required this.icon});

  final String text;
  final IconData icon;

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: LpgSpacing.sm),
      child: Row(
        children: [
          Icon(icon, size: LpgSizes.iconMd, color: colors.textSecondary),
          const SizedBox(width: LpgSpacing.smd),
          Expanded(
            child: Text(
              text,
              style: context.lpgText.bodyMedium?.copyWith(
                color: colors.textSecondary,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
