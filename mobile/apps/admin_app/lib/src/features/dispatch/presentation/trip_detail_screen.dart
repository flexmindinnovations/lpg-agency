import 'package:api_client/api_client.dart';
import 'package:core/core.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../api_result.dart';
import '../../../providers.dart';
import '../../orders/data/orders_provider.dart';
import '../data/dispatch_provider.dart';
import '../data/trip_detail_provider.dart';
import '../domain/trip_status.dart';
import 'settle_trip_sheet.dart';

/// One trip: who is driving, where the stops are and in what order, what is
/// on the van, the load-out checks, and what the driver owes. Dispatch can
/// re-order the stops, cancel a trip that hasn't left, and settle one that
/// has come back.
class TripDetailScreen extends ConsumerStatefulWidget {
  const TripDetailScreen({super.key, required this.tripId});

  final String tripId;

  @override
  ConsumerState<TripDetailScreen> createState() => _TripDetailScreenState();
}

class _TripDetailScreenState extends ConsumerState<TripDetailScreen> {
  var _busy = false;

  void _refresh() {
    ref.invalidate(tripProvider(widget.tripId));
    ref.invalidate(tripWeighmentsProvider(widget.tripId));
    ref.invalidate(tripCashProvider(widget.tripId));
    ref.invalidate(dispatchTripsProvider);
    ref.invalidate(pastTripsProvider);
    ref.invalidate(ordersWaitingForTripProvider);
    ref.invalidate(activeTripsProvider);
  }

  void _toast(String message, {LpgTone tone = LpgTone.success}) =>
      LpgFeedback.showToast(context, message, tone: tone);

  Future<void> _optimise() async {
    setState(() => _busy = true);
    final result = await ref
        .read(routeApiProvider)
        .optimizeRoute(widget.tripId);
    if (!mounted) return;
    setState(() => _busy = false);
    switch (result) {
      case FailureResult<RouteOptimization>(:final failure):
        _toast(failure.message, tone: LpgTone.danger);
      case Success<RouteOptimization>(:final value):
        _refresh();
        _toast(
          value.kmSaved > 0.05
              ? 'Stops re-ordered. About ${value.kmSaved.toStringAsFixed(1)} km shorter.'
              : 'Stops are already in a good order.',
        );
    }
  }

  Future<void> _cancel() async {
    final ok = await LpgFeedback.confirm(
      context,
      title: 'Cancel this trip?',
      message:
          'The orders on it go back to waiting for a trip, and anything '
          'already loaded on the van is returned to stock.',
      confirmLabel: 'Cancel trip',
      cancelLabel: 'Keep trip',
      destructive: true,
    );
    if (!ok || !mounted) return;
    setState(() => _busy = true);
    final result = await ref.read(routeApiProvider).cancelRoute(widget.tripId);
    if (!mounted) return;
    setState(() => _busy = false);
    switch (result) {
      case FailureResult<RouteSummary>(:final failure):
        _toast(failure.message, tone: LpgTone.danger);
      case Success<RouteSummary>():
        _refresh();
        _toast('Trip cancelled.');
    }
  }

  Future<void> _settle(RouteSummary trip) async {
    final done = await LpgFeedback.showSheet<bool>(
      context,
      title: 'Settle trip',
      builder: (_) => SettleTripSheet(trip: trip),
    );
    if (done != true || !mounted) return;
    _refresh();
    _toast('Trip settled.');
  }

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;
    final text = context.lpgText;
    final tripAsync = ref.watch(tripProvider(widget.tripId));
    final fleet = ref.watch(fleetProvider).value;
    final names = ref.watch(cylinderNamesProvider).value ?? const {};

    return Scaffold(
      appBar: AppBar(
        title: const Text('Trip'),
        actions: [
          IconButton(
            tooltip: 'Refresh',
            icon: const Icon(LpgIcons.sync),
            onPressed: _refresh,
          ),
        ],
      ),
      body: tripAsync.when(
        loading: () => const Padding(
          padding: LpgSpacing.page,
          child: LpgSkeletonList(itemCount: 4),
        ),
        error: (err, _) => LpgErrorState(
          message: errorMessage(err),
          onRetry: () => ref.invalidate(tripProvider(widget.tripId)),
        ),
        data: (trip) {
          final pending = trip.stops.where((s) => s.status == 'pending').length;
          final canOptimise =
              pending >= 2 &&
              (trip.status == 'planned' ||
                  trip.status == 'loaded' ||
                  trip.status == 'in_progress');
          final canCancel = trip.status == 'planned' || trip.status == 'loaded';
          final stops = [...trip.stops]
            ..sort((a, b) => a.sequenceNumber.compareTo(b.sequenceNumber));

          return RefreshIndicator(
            onRefresh: () async {
              _refresh();
              await ref.read(tripProvider(widget.tripId).future);
            },
            child: ListView(
              physics: const AlwaysScrollableScrollPhysics(),
              padding: LpgSpacing.page.copyWith(bottom: LpgSpacing.xxl),
              children: [
                LpgCard(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Expanded(
                            child: Text(
                              fleet == null
                                  ? 'Trip'
                                  : '${fleet.driverName(trip.driverId)} · '
                                        '${fleet.vehicleName(trip.vehicleId)}',
                              style: text.titleMedium,
                            ),
                          ),
                          LpgStatusBadge(
                            label: tripStatusLabel(trip.status),
                            severity: tripStatusSeverity(trip.status),
                          ),
                        ],
                      ),
                      if (trip.date != null)
                        Text(
                          LpgFormat.date(trip.date!.toLocal()),
                          style: text.bodySmall?.copyWith(
                            color: colors.textSecondary,
                          ),
                        ),
                    ],
                  ),
                ),
                const SizedBox(height: LpgSpacing.md),
                if (trip.status == 'completed')
                  LpgBanner(
                    tone: LpgTone.info,
                    message:
                        'The trip is back. Count what is left on the van, '
                        'then settle it to close it out.',
                    actionLabel: 'Settle trip',
                    onAction: _busy ? null : () => _settle(trip),
                  ),
                if (trip.status == 'completed')
                  const SizedBox(height: LpgSpacing.md),
                Text('Stops', style: text.titleMedium),
                const SizedBox(height: LpgSpacing.sm),
                if (stops.isEmpty)
                  Text(
                    'No orders on this trip.',
                    style: text.bodyMedium?.copyWith(
                      color: colors.textSecondary,
                    ),
                  ),
                for (final stop in stops)
                  LpgListTile(
                    title:
                        '${stop.sequenceNumber}. '
                        '${LpgFormat.orderNumber(stop.orderNumber, stop.orderId)}',
                    subtitle: LpgFormat.statusLabel(stop.status),
                    showChevron: true,
                    onTap: () => context.goNamed(
                      'order_detail',
                      pathParameters: {'orderId': stop.orderId},
                    ),
                  ),
                if (canOptimise) ...[
                  const SizedBox(height: LpgSpacing.sm),
                  LpgButton(
                    label: 'Re-order stops for a shorter drive',
                    icon: LpgIcons.route,
                    variant: LpgButtonVariant.secondary,
                    expand: true,
                    isLoading: _busy,
                    onPressed: _busy ? null : _optimise,
                  ),
                ],
                if (trip.loadedLines.isNotEmpty) ...[
                  const SizedBox(height: LpgSpacing.lg),
                  Text('On the van', style: text.titleMedium),
                  const SizedBox(height: LpgSpacing.sm),
                  for (final line in trip.loadedLines)
                    LpgKeyValueRow(
                      label: names[line.cylinderTypeId] ?? 'Cylinder',
                      value: '${line.quantity}',
                    ),
                  if (trip.loadConfirmedAt != null)
                    Text(
                      'Driver confirmed the load '
                      '${LpgFormat.dateTime(trip.loadConfirmedAt!.toLocal())}.',
                      style: text.bodySmall?.copyWith(
                        color: colors.textSecondary,
                      ),
                    ),
                ],
                _Weighments(tripId: widget.tripId, names: names),
                _Cash(tripId: widget.tripId, tripStatus: trip.status),
                if (canCancel) ...[
                  const SizedBox(height: LpgSpacing.xl),
                  LpgButton(
                    label: 'Cancel trip',
                    variant: LpgButtonVariant.destructive,
                    expand: true,
                    onPressed: _busy ? null : _cancel,
                  ),
                ],
                if (trip.status == 'completed') ...[
                  const SizedBox(height: LpgSpacing.xl),
                  LpgButton(
                    label: 'Settle trip',
                    icon: LpgIcons.check,
                    expand: true,
                    onPressed: _busy ? null : () => _settle(trip),
                  ),
                ],
              ],
            ),
          );
        },
      ),
    );
  }
}

class _Weighments extends ConsumerWidget {
  const _Weighments({required this.tripId, required this.names});

  final String tripId;
  final Map<String, String> names;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final records = ref.watch(tripWeighmentsProvider(tripId)).value ?? const [];
    if (records.isEmpty) return const SizedBox.shrink();
    final text = context.lpgText;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const SizedBox(height: LpgSpacing.lg),
        Text('Weight checks', style: text.titleMedium),
        const SizedBox(height: LpgSpacing.sm),
        for (final r in records)
          LpgKeyValueRow(
            label: names[r.cylinderTypeId] ?? 'Cylinder',
            value:
                '${r.cylindersChecked} weighed · '
                '${r.underweightCylinderCount} short · '
                '${LpgFormat.statusLabel(r.result)}',
          ),
      ],
    );
  }
}

/// A read-only line for the trip's cash: what the driver owes and whether a
/// handover was declared. Recording and reviewing handovers lives in
/// Approvals.
class _Cash extends ConsumerWidget {
  const _Cash({required this.tripId, required this.tripStatus});

  final String tripId;
  final String tripStatus;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    if (tripStatus != 'completed' && tripStatus != 'reconciled') {
      return const SizedBox.shrink();
    }
    final cash = ref.watch(tripCashProvider(tripId)).value;
    if (cash == null) return const SizedBox.shrink();
    final text = context.lpgText;
    final handover = cash.handover;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const SizedBox(height: LpgSpacing.lg),
        Text('Cash', style: text.titleMedium),
        const SizedBox(height: LpgSpacing.sm),
        LpgKeyValueRow(
          label: 'Cash to collect',
          value:
              '${LpgFormat.currency(cash.expectedAmount)} '
              '(${cash.cashStopCount} cash '
              '${cash.cashStopCount == 1 ? 'stop' : 'stops'})',
        ),
        LpgKeyValueRow(
          label: 'Handed over',
          value: handover == null
              ? 'Not declared yet'
              : '${LpgFormat.currency(handover.actualAmount)}'
                    '${handover.shortfall > 0 ? ' · short ${LpgFormat.currency(handover.shortfall)}' : ''}',
        ),
      ],
    );
  }
}
