import 'dart:async';

import 'package:api_client/api_client.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../compliance/data/compliance_provider.dart';
import '../../../i18n/admin_strings.dart';
import '../../../shared/admin_app_bar.dart';
import '../../../shared/metric_tile.dart';
import '../../approvals/data/approvals_provider.dart';
import '../../dispatch/data/dispatch_provider.dart';
import '../../dispatch/domain/trip_status.dart';
import '../../orders/data/orders_provider.dart';
import '../data/dashboard_providers.dart';

/// How often the dashboard re-reads its numbers while it is on screen. The
/// realtime feed refreshes it the moment an order moves; this is the safety
/// net for changes the feed does not announce (a new complaint, stock).
const _liveRefresh = Duration(seconds: 45);

/// The owner's home screen: every number is live and opens the screen that
/// is behind it.
class DashboardScreen extends ConsumerStatefulWidget {
  const DashboardScreen({super.key});

  @override
  ConsumerState<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends ConsumerState<DashboardScreen>
    with WidgetsBindingObserver {
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _timer = Timer.periodic(_liveRefresh, (_) => _refresh());
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _timer?.cancel();
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) _refresh();
  }

  void _refresh() {
    if (!mounted) return;
    ref.invalidate(dashboardSummaryProvider);
    ref.invalidate(operationsSnapshotProvider);
    ref.invalidate(dispatchTripsProvider);
    ref.invalidate(fleetProvider);
    ref.invalidate(pendingCashHandoversProvider);
    ref.invalidate(complianceDueCountProvider);
  }

  void _orders(String filter) =>
      context.goNamed('orders', queryParameters: {'filter': filter});

  @override
  Widget build(BuildContext context) {
    final opsAsync = ref.watch(operationsSnapshotProvider);
    final summaryAsync = ref.watch(dashboardSummaryProvider);
    final fleet = ref.watch(fleetProvider).value;
    final trips = ref.watch(dispatchTripsProvider).value;

    return Scaffold(
      appBar: AdminAppBar(
        title: 'Dashboard',
        actions: [
          IconButton(
            tooltip: 'New order',
            icon: const Icon(LpgIcons.add),
            onPressed: () => context.goNamed('order_new'),
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: () async {
          _refresh();
          await ref.read(operationsSnapshotProvider.future);
        },
        child: ListView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: LpgSpacing.page,
          children: [
            const _LiveStamp(),
            const SizedBox(height: LpgSpacing.sm),
            LpgAsyncView<OperationsSnapshotResponse>(
              value: opsAsync,
              onRetry: () => ref.invalidate(operationsSnapshotProvider),
              // The hero and the metric grid, where the real ones will be.
              skeleton: const LpgSkeletonGroup(
                children: [
                  LpgSkeletonHero(),
                  LpgSkeletonTileGrid(columns: 2, rows: 3),
                ],
              ),
              data: (context, ops) => _Body(
                ops: ops,
                fleet: fleet,
                trips: trips,
                complianceDue: ref.watch(complianceDueCountProvider).value ?? 0,
                onOrders: _orders,
              ),
            ),
            const SizedBox(height: LpgSpacing.lg),
            LpgAsyncView<DashboardSummaryResponse>(
              value: summaryAsync,
              onRetry: () => ref.invalidate(dashboardSummaryProvider),
              // One notice on the screen is enough: the numbers above carry it.
              showStaleNotice: false,
              skeleton: const LpgSkeletonGroup(
                children: [
                  LpgSkeletonCard(lines: 3),
                  LpgSkeletonCard(lines: 4),
                ],
              ),
              data: (context, summary) => _Summary(summary: summary),
            ),
          ],
        ),
      ),
    );
  }
}

/// "Live" dot and the time of the last read, so the owner can trust what
/// they are looking at.
class _LiveStamp extends ConsumerWidget {
  const _LiveStamp();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final colors = context.lpgColors;
    final text = context.lpgText;
    final loading = ref.watch(operationsSnapshotProvider).isLoading;
    return Row(
      children: [
        Icon(
          LpgIcons.liveDot,
          size: LpgSizes.iconSm,
          color: loading ? colors.textSecondary : colors.statusSuccess,
        ),
        const SizedBox(width: LpgSpacing.xs),
        Text(
          loading ? 'Updating…' : 'Live · pull down to refresh',
          style: text.bodySmall?.copyWith(color: colors.textSecondary),
        ),
      ],
    );
  }
}

class _Body extends StatelessWidget {
  const _Body({
    required this.ops,
    required this.fleet,
    required this.trips,
    required this.complianceDue,
    required this.onOrders,
  });

  final OperationsSnapshotResponse ops;
  final int complianceDue;
  final FleetData? fleet;
  final List<RouteSummary>? trips;
  final void Function(String filter) onOrders;

  int _open(String status) => ops.orders.openByStatus[status] ?? 0;

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;
    final text = context.lpgText;
    final o = ops.orders;

    final busyDrivers = {
      for (final t in trips ?? const <RouteSummary>[]) t.driverId,
    };
    final busyVans = {
      for (final t in trips ?? const <RouteSummary>[]) t.vehicleId,
    };
    final activeDrivers = [
      for (final d in fleet?.drivers ?? const <FleetDriver>[])
        if (d.isActive) d,
    ];
    final activeVans = [
      for (final v in fleet?.vehicles ?? const <FleetVehicle>[])
        if (v.isActive) v,
    ];
    final freeDrivers = activeDrivers
        .where((d) => !busyDrivers.contains(d.id))
        .length;
    final freeVans = activeVans.where((v) => !busyVans.contains(v.id)).length;

    final waiting = _open('confirmed');
    final booked = _open('booked');
    final outNow = _open('out_for_delivery');
    final cash = ops.cash;
    final inv = ops.invoices;

    final children = <Widget>[
      LpgHeroCard(
        onTap: () => onOrders('All'),
        watermark: LpgIcons.orders,
        keepClearOfWatermark: true,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              "Today's bookings",
              style: text.bodyMedium?.copyWith(color: colors.onHero),
            ),
            const SizedBox(height: LpgSpacing.xs),
            Text(
              '${o.bookingsToday}',
              style: text.displaySmall?.copyWith(color: colors.onHero),
            ),
            const SizedBox(height: LpgSpacing.md),
            LpgHeroStats(
              stats: [
                LpgHeroStat(
                  value: '${o.deliveredToday}',
                  label: context.strings.dashboard.hero.delivered,
                ),
                LpgHeroStat(
                  value: '${o.failedToday}',
                  label: context.strings.dashboard.hero.failed,
                ),
                LpgHeroStat(
                  value: '${o.pendingCancellations}',
                  label: context.strings.dashboard.hero.toApprove,
                ),
              ],
            ),
          ],
        ),
      ),
      const SizedBox(height: LpgSpacing.lg),
      _Attention(
        items: [
          if (booked > 0)
            _AttentionItem(
              icon: LpgIcons.pending,
              tone: LpgTone.warning,
              title:
                  '$booked ${booked == 1 ? 'booking is' : 'bookings are'} waiting to be confirmed',
              action: 'Confirm',
              onTap: () => onOrders('Booked'),
            ),
          if (waiting > 0)
            _AttentionItem(
              icon: LpgIcons.truck,
              tone: LpgTone.info,
              title:
                  '$waiting confirmed ${waiting == 1 ? 'order needs' : 'orders need'} a van',
              action: 'Send out',
              onTap: () => context.goNamed('dispatch'),
            ),
          if (o.failedToday > 0)
            _AttentionItem(
              icon: LpgIcons.warning,
              tone: LpgTone.danger,
              title:
                  '${o.failedToday} failed ${o.failedToday == 1 ? 'delivery' : 'deliveries'} to reschedule',
              action: 'Open',
              onTap: () => onOrders('Failed'),
            ),
          if (o.pendingCancellations > 0)
            _AttentionItem(
              icon: LpgIcons.cancel,
              tone: LpgTone.danger,
              title:
                  '${o.pendingCancellations} cancellation ${o.pendingCancellations == 1 ? 'request needs' : 'requests need'} your decision',
              action: 'Review',
              onTap: () => onOrders('Out for delivery'),
            ),
          if (ops.openComplaints > 0)
            _AttentionItem(
              icon: LpgIcons.complaint,
              tone: LpgTone.warning,
              title:
                  '${ops.openComplaints} open ${ops.openComplaints == 1 ? 'complaint' : 'complaints'} to handle',
              action: 'Open',
              onTap: () => context.pushNamed('complaints'),
            ),
          if (complianceDue > 0)
            _AttentionItem(
              icon: LpgIcons.badge,
              tone: LpgTone.danger,
              title:
                  '$complianceDue ${complianceDue == 1 ? 'licence or paper needs' : 'licences or papers need'} renewing',
              action: 'Renew',
              onTap: () => context.pushNamed('compliance'),
            ),
          if ((cash?.handoversAwaitingReview ?? 0) > 0)
            _AttentionItem(
              icon: LpgIcons.cash,
              tone: LpgTone.accent,
              title:
                  '${cash!.handoversAwaitingReview} driver cash ${cash.handoversAwaitingReview == 1 ? 'handover' : 'handovers'} to review',
              action: 'Review',
              onTap: () => context.pushNamed('approvals'),
            ),
          if (fleet != null &&
              (freeDrivers == 0 || freeVans == 0) &&
              waiting > 0)
            _AttentionItem(
              icon: LpgIcons.van,
              tone: LpgTone.warning,
              title: freeVans == 0 && freeDrivers == 0
                  ? 'No free van or driver for the waiting orders'
                  : freeVans == 0
                  ? 'No free van for the waiting orders'
                  : 'No free driver for the waiting orders',
              action: 'Fix',
              onTap: () => context.pushNamed('fleet'),
            ),
        ],
      ),
      const SizedBox(height: LpgSpacing.lg),
      SectionHeading(
        'Live trips',
        actionLabel: 'All trips',
        onAction: () => context.goNamed('dispatch'),
      ),
      _LiveTrips(trips: trips, fleet: fleet),
      const SizedBox(height: LpgSpacing.lg),
      const SectionHeading('Orders right now'),
      MetricGrid(
        tiles: [
          MetricTile(
            label: 'Awaiting confirmation',
            value: '$booked',
            icon: LpgIcons.pending,
            tone: LpgTone.warning,
            attention: booked > 0,
            onTap: () => onOrders('Booked'),
          ),
          MetricTile(
            label: 'Ready to send out',
            value: '$waiting',
            icon: LpgIcons.truck,
            tone: LpgTone.info,
            attention: waiting > 0,
            onTap: () => context.goNamed('dispatch'),
          ),
          MetricTile(
            label: 'Out for delivery',
            value: '$outNow',
            icon: LpgIcons.navigate,
            onTap: () => onOrders('Out for delivery'),
          ),
          MetricTile(
            label: 'Failed today',
            value: '${o.failedToday}',
            icon: LpgIcons.warning,
            tone: LpgTone.danger,
            attention: o.failedToday > 0,
            onTap: () => onOrders('Failed'),
          ),
        ],
      ),
      SectionHeading(
        'Drivers and vans',
        actionLabel: 'Manage',
        onAction: () => context.pushNamed('fleet'),
      ),
      MetricGrid(
        tiles: [
          MetricTile(
            label: 'Drivers free',
            value: fleet == null
                ? '–'
                : '$freeDrivers of ${activeDrivers.length}',
            icon: LpgIcons.user,
            tone: freeDrivers == 0 && fleet != null
                ? LpgTone.warning
                : LpgTone.success,
            attention: fleet != null && freeDrivers == 0,
            onTap: () =>
                context.pushNamed('fleet', queryParameters: {'tab': 'drivers'}),
          ),
          MetricTile(
            label: 'Vans free',
            value: fleet == null ? '–' : '$freeVans of ${activeVans.length}',
            icon: LpgIcons.van,
            tone: freeVans == 0 && fleet != null
                ? LpgTone.warning
                : LpgTone.success,
            attention: fleet != null && freeVans == 0,
            onTap: () =>
                context.pushNamed('fleet', queryParameters: {'tab': 'vans'}),
          ),
        ],
      ),
      const SectionHeading('Money and watch-list'),
      MetricGrid(
        tiles: [
          MetricTile(
            label: 'Cash with drivers',
            value: LpgFormat.currencyWhole(cash?.awaitingHandover ?? 0),
            caption: (cash?.handoversAwaitingReview ?? 0) > 0
                ? '${cash!.handoversAwaitingReview} to review'
                : null,
            icon: LpgIcons.cash,
            tone: LpgTone.accent,
            attention: (cash?.handoversAwaitingReview ?? 0) > 0,
            onTap: () => context.pushNamed('cash_book'),
          ),
          MetricTile(
            label: 'Outstanding',
            value: LpgFormat.currencyWhole(inv?.outstandingAmount ?? 0),
            caption: '${inv?.outstandingCount ?? 0} invoices',
            icon: LpgIcons.invoice,
            onTap: () => context.pushNamed('invoices'),
          ),
          MetricTile(
            label: 'Overdue',
            value: LpgFormat.currencyWhole(inv?.overdueAmount ?? 0),
            caption: '${inv?.overdueCount ?? 0} invoices',
            icon: LpgIcons.clock,
            tone: LpgTone.danger,
            attention: (inv?.overdueCount ?? 0) > 0,
            onTap: () => context.pushNamed('invoices'),
          ),
          MetricTile(
            label: 'Open complaints',
            value: '${ops.openComplaints}',
            icon: LpgIcons.complaint,
            tone: LpgTone.warning,
            attention: ops.openComplaints > 0,
            onTap: () => context.pushNamed('complaints'),
          ),
          MetricTile(
            label: 'Low-stock godowns',
            value: '${ops.lowStockCount}',
            icon: LpgIcons.warehouse,
            tone: LpgTone.danger,
            attention: ops.lowStockCount > 0,
            onTap: () => context.pushNamed('stock'),
          ),
        ],
      ),
    ];

    // Index 6 is the gap after the live trips; what follows is the metric
    // grids, which sit in their own column on a tablet.
    const split = 6;
    if (!LpgBreakpoints.isExpanded(context)) {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: children,
      );
    }
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: children.sublist(0, split),
          ),
        ),
        const SizedBox(width: LpgSpacing.lg),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: children.sublist(split + 1),
          ),
        ),
      ],
    );
  }
}

class _Summary extends StatelessWidget {
  const _Summary({required this.summary});

  final DashboardSummaryResponse summary;

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;
    final text = context.lpgText;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const SectionHeading("Today's prices"),
        SizedBox(
          height: 84,
          child: ListView.separated(
            scrollDirection: Axis.horizontal,
            itemCount: summary.priceCards.length,
            separatorBuilder: (_, _) => const SizedBox(width: LpgSpacing.sm),
            itemBuilder: (context, i) {
              final card = summary.priceCards[i];
              return SizedBox(
                width: 168,
                child: LpgCard(
                  padding: const EdgeInsets.all(LpgSpacing.smd),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Text(
                        card.name,
                        style: text.bodySmall?.copyWith(
                          color: colors.textSecondary,
                        ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                      Text(
                        LpgFormat.currency(card.price),
                        style: text.titleMedium?.copyWith(
                          color: colors.actionPrimary,
                        ),
                      ),
                    ],
                  ),
                ),
              );
            },
          ),
        ),
      ],
    );
  }
}

class _AttentionItem {
  const _AttentionItem({
    required this.icon,
    required this.tone,
    required this.title,
    required this.action,
    required this.onTap,
  });

  final IconData icon;
  final LpgTone tone;
  final String title;
  final String action;
  final VoidCallback onTap;
}

/// The things that need the owner right now, one tappable card each. When
/// there are none it says so, rather than leaving a gap.
class _Attention extends StatelessWidget {
  const _Attention({required this.items});

  final List<_AttentionItem> items;

  @override
  Widget build(BuildContext context) {
    final text = context.lpgText;
    final colors = context.lpgColors;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const SectionHeading('Needs your attention'),
        if (items.isEmpty)
          LpgCard(
            variant: LpgCardVariant.tonal,
            tone: LpgTone.success,
            child: Row(
              children: [
                const LpgIconBox(icon: LpgIcons.allDone, tone: LpgTone.success),
                const SizedBox(width: LpgSpacing.md),
                Expanded(
                  child: Text(
                    'All caught up. Nothing is waiting on you.',
                    style: text.bodyLarge,
                  ),
                ),
              ],
            ),
          )
        else
          LpgGroupedList(
            children: [
              for (final item in items)
                LpgListTile(
                  leadingIcon: item.icon,
                  leadingTone: item.tone,
                  title: item.title,
                  trailing: Text(
                    item.action,
                    style: text.labelLarge?.copyWith(
                      color: item.tone.foreground(colors),
                    ),
                  ),
                  showChevron: true,
                  onTap: item.onTap,
                ),
            ],
          ),
      ],
    );
  }
}

/// Every trip that is loading or on the road, with how far through its stops
/// it is. Tapping one opens it.
class _LiveTrips extends StatelessWidget {
  const _LiveTrips({required this.trips, required this.fleet});

  final List<RouteSummary>? trips;
  final FleetData? fleet;

  @override
  Widget build(BuildContext context) {
    final text = context.lpgText;
    final colors = context.lpgColors;
    final list = trips;

    if (list == null) return const LpgSkeleton(height: 84);
    if (list.isEmpty) {
      return LpgCard(
        onTap: () => context.goNamed('dispatch'),
        child: Row(
          children: [
            const LpgIconBox(icon: LpgIcons.truck, tone: LpgTone.neutral),
            const SizedBox(width: LpgSpacing.md),
            Expanded(
              child: Text(
                'No trips on the road. Plan one from Dispatch.',
                style: text.bodyLarge,
              ),
            ),
            Icon(LpgIcons.chevronRight, color: colors.textSecondary),
          ],
        ),
      );
    }

    return LpgGroupedList(
      children: [
        for (final trip in list.take(4))
          Builder(
            builder: (context) {
              final total = trip.stops.length;
              final done = trip.stops
                  .where((s) => s.status != 'pending')
                  .length;
              final severity = tripStatusSeverity(trip.status);
              return Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  LpgListTile(
                    leadingIcon: LpgIcons.truck,
                    leadingTone: severity.tone,
                    title: fleet == null
                        ? 'Trip'
                        : '${fleet!.vehicleName(trip.vehicleId)} · '
                              '${fleet!.driverName(trip.driverId)}',
                    subtitle: total == 0
                        ? 'No orders on this trip yet'
                        : '$done of $total ${total == 1 ? 'stop' : 'stops'} done',
                    trailing: LpgStatusBadge(
                      label: tripStatusLabel(trip.status),
                      severity: severity,
                    ),
                    showChevron: true,
                    onTap: () => context.pushNamed(
                      'trip_detail',
                      pathParameters: {'tripId': trip.id},
                    ),
                  ),
                  if (total > 0)
                    Padding(
                      padding: const EdgeInsets.fromLTRB(
                        LpgSpacing.md,
                        0,
                        LpgSpacing.md,
                        LpgSpacing.smd,
                      ),
                      child: ClipRRect(
                        borderRadius: BorderRadius.circular(LpgRadius.full),
                        child: LinearProgressIndicator(
                          value: done / total,
                          minHeight: 6,
                          backgroundColor: colors.borderDefault,
                        ),
                      ),
                    ),
                ],
              );
            },
          ),
      ],
    );
  }
}
