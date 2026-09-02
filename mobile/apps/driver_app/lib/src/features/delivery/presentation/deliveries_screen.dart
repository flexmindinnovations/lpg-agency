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
    final theme = Theme.of(context);
    final colors = theme.extension<LpgColors>()!;
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
          padding: const EdgeInsets.all(16),
          children: [
            _sectionLabel(theme, colors, 'Current route'),
            const SizedBox(height: 8),
            routeAsync.when(
              loading: () => const Padding(
                padding: EdgeInsets.symmetric(vertical: 24),
                child: Center(child: LpgLoadingIndicator()),
              ),
              error: (err, _) => LpgEmptyState(
                message: 'Could not load your route.\n$err',
                icon: Icons.error_outline,
                actionLabel: 'Retry',
                onAction: () => ref.invalidate(activeRouteProvider),
              ),
              data: (route) {
                if (route == null) {
                  return const _MutedNote('No active route right now.');
                }
                return Column(
                  children: [
                    for (final stop in route.stops)
                      StopTile(
                        stop: stop,
                        onTap: () => context.pushNamed(
                          'stop',
                          pathParameters: {'orderId': stop.orderId},
                        ),
                      ),
                  ],
                );
              },
            ),
            const SizedBox(height: 24),
            _sectionLabel(theme, colors, 'Past routes'),
            const SizedBox(height: 8),
            historyAsync.when(
              loading: () => const Padding(
                padding: EdgeInsets.symmetric(vertical: 24),
                child: Center(child: LpgLoadingIndicator()),
              ),
              error: (err, _) => const _MutedNote('Could not load history.'),
              data: (routes) {
                if (routes.isEmpty) {
                  return const _MutedNote('No finished routes yet.');
                }
                final pendingCashRouteId = ref
                    .watch(pendingCashHandoverProvider)
                    .value
                    ?.routeId;
                return Column(
                  children: [
                    for (final r in routes)
                      _HistoryRow(
                        route: r,
                        cashPending: r.id == pendingCashRouteId,
                        onTap: r.status == 'completed'
                            ? () => context.pushNamed(
                                'cashHandover',
                                pathParameters: {'routeId': r.id},
                              )
                            : null,
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

  Widget _sectionLabel(ThemeData theme, LpgColors colors, String text) => Text(
    text,
    style: theme.textTheme.titleMedium?.copyWith(
      fontWeight: FontWeight.w600,
      color: colors.textPrimary,
    ),
  );
}

class _HistoryRow extends StatelessWidget {
  const _HistoryRow({required this.route, this.cashPending = false, this.onTap});

  final RouteSummary route;
  final bool cashPending;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).extension<LpgColors>()!;
    final date = route.date;
    final dateLabel = date == null
        ? 'Route'
        : '${date.year}-${_two(date.month)}-${_two(date.day)}';
    final n = route.stops.length;
    return LpgCard(
      padding: EdgeInsets.zero,
      onTap: onTap,
      child: LpgListTile(
        leadingIcon: Icons.history,
        title: dateLabel,
        subtitle:
            '$n stop${n == 1 ? '' : 's'} · '
            '${route.status.replaceAll('_', ' ')}',
        trailing: cashPending
            ? const LpgStatusBadge(
                label: 'CASH PENDING',
                severity: LpgStatusSeverity.warning,
              )
            : Icon(
                route.status == 'cancelled'
                    ? Icons.cancel_outlined
                    : Icons.check_circle_outline,
                color: route.status == 'cancelled'
                    ? colors.statusDanger
                    : colors.statusSuccess,
              ),
      ),
    );
  }

  String _two(int v) => v.toString().padLeft(2, '0');
}

class _MutedNote extends StatelessWidget {
  const _MutedNote(this.text);

  final String text;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colors = theme.extension<LpgColors>()!;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Text(
        text,
        style: theme.textTheme.bodyMedium?.copyWith(
          color: colors.textSecondary,
        ),
      ),
    );
  }
}
