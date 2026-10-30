import 'package:api_client/api_client.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:core/core.dart';

import '../../../api_result.dart';
import '../../../providers.dart';
import '../../../shared/admin_app_bar.dart';
import '../../../shared/order_row.dart';
import '../../orders/data/orders_provider.dart';
import '../../orders/presentation/sheets/send_out_sheet.dart';
import '../data/dispatch_provider.dart';
import '../domain/trip_status.dart';

/// The trip sheet: confirmed orders waiting for a van, and the trips that
/// are loading or out. "Send out" opens the same sheet as the order page
/// (pick a driver and van, load, hand over in one step).
class DispatchScreen extends ConsumerStatefulWidget {
  const DispatchScreen({super.key});

  @override
  ConsumerState<DispatchScreen> createState() => _DispatchScreenState();
}

class _DispatchScreenState extends ConsumerState<DispatchScreen> {
  /// Show finished and cancelled trips instead of the ones still going.
  var _past = false;

  Future<void> _sendOut(
    BuildContext context,
    WidgetRef ref,
    OrderResponse order,
  ) async {
    final done = await LpgFeedback.showSheet<bool>(
      context,
      title: 'Send out ${LpgFormat.orderNumber(order.orderNumber, order.id)}',
      builder: (_) => SendOutSheet(order: order),
    );
    if (done != true || !context.mounted) return;
    LpgFeedback.showToast(
      context,
      'Loaded and handed to the driver.',
      tone: LpgTone.success,
    );
    _refresh(ref);
  }

  void _refresh(WidgetRef ref) {
    ref.invalidate(dispatchTripsProvider);
    ref.invalidate(pastTripsProvider);
    ref.invalidate(ordersWaitingForTripProvider);
    ref.invalidate(adminOrdersProvider);
    ref.invalidate(activeTripsProvider);
  }

  Future<void> _cancelTrip(RouteSummary trip) async {
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
    final result = await ref.read(routeApiProvider).cancelRoute(trip.id);
    if (!mounted) return;
    switch (result) {
      case FailureResult<RouteSummary>(:final failure):
        LpgFeedback.showToast(context, failure.message, tone: LpgTone.danger);
      case Success<RouteSummary>():
        _refresh(ref);
        LpgFeedback.showToast(
          context,
          'Trip cancelled.',
          tone: LpgTone.success,
        );
    }
  }

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;
    final text = context.lpgText;
    final tripsAsync = ref.watch(
      _past ? pastTripsProvider : dispatchTripsProvider,
    );
    final waitingAsync = ref.watch(ordersWaitingForTripProvider);
    final fleet = ref.watch(fleetProvider).value;
    final names = ref.watch(cylinderNamesProvider).value ?? const {};

    return Scaffold(
      appBar: AdminAppBar(
        title: 'Dispatch',
        actions: [
          IconButton(
            tooltip: 'Drivers and vans',
            icon: const Icon(LpgIcons.user),
            onPressed: () => context.pushNamed('fleet'),
          ),
          IconButton(
            tooltip: 'Refresh',
            icon: const Icon(LpgIcons.sync),
            onPressed: () => _refresh(ref),
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: () async {
          _refresh(ref);
          await ref.read(
            _past ? pastTripsProvider.future : dispatchTripsProvider.future,
          );
        },
        child: ListView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: LpgSpacing.page,
          children: [
            if (fleet != null &&
                (!fleet.drivers.any((d) => d.isActive) ||
                    !fleet.vehicles.any((v) => v.isActive))) ...[
              LpgBanner(
                tone: LpgTone.warning,
                message: !fleet.drivers.any((d) => d.isActive)
                    ? 'No active driver. Add or activate one to send orders out.'
                    : 'No active van. Add or activate one to send orders out.',
                actionLabel: 'Drivers and vans',
                onAction: () => context.pushNamed('fleet'),
              ),
              const SizedBox(height: LpgSpacing.md),
            ],
            Text('Waiting for a trip', style: text.titleMedium),
            const SizedBox(height: LpgSpacing.sm),
            waitingAsync.when(
              loading: () => const LpgSkeleton(height: 72),
              error: (err, _) => LpgErrorState(
                message: errorMessage(err),
                onRetry: () => ref.invalidate(ordersWaitingForTripProvider),
              ),
              data: (orders) {
                if (orders.isEmpty) {
                  return Text(
                    'Every confirmed order is on a trip.',
                    style: text.bodyMedium?.copyWith(
                      color: colors.textSecondary,
                    ),
                  );
                }
                return LpgGroupedList(
                  children: [
                    for (final order in orders)
                      OrderTile(
                        order: order,
                        subtitle:
                            '${order.customerName ?? 'Customer'}  ·  '
                            '${[for (final l in order.lines) '${l.quantityOrdered} × ${names[l.cylinderTypeId] ?? 'Cylinder'}'].join(', ')}',
                        onTap: () => context.goNamed(
                          'order_detail',
                          pathParameters: {'orderId': order.id},
                        ),
                        trailing: LpgButton(
                          label: 'Send out',
                          icon: LpgIcons.truck,
                          variant: LpgButtonVariant.text,
                          onPressed: () => _sendOut(context, ref, order),
                        ),
                      ),
                  ],
                );
              },
            ),
            const SizedBox(height: LpgSpacing.lg),
            Text('Trips', style: text.titleMedium),
            const SizedBox(height: LpgSpacing.sm),
            LpgChoiceChips<bool>(
              options: const {false: 'On now', true: 'Past'},
              selected: _past,
              onSelected: (v) => setState(() => _past = v ?? false),
            ),
            const SizedBox(height: LpgSpacing.sm),
            tripsAsync.when(
              loading: () => const LpgSkeletonList(itemCount: 3),
              error: (err, _) => LpgErrorState(
                message: errorMessage(err),
                onRetry: () => ref.invalidate(
                  _past ? pastTripsProvider : dispatchTripsProvider,
                ),
              ),
              data: (trips) {
                if (trips.isEmpty) {
                  return LpgEmptyState(
                    message: _past
                        ? 'No finished or cancelled trips yet.'
                        : 'No trips are loading or on the road.',
                    icon: LpgIcons.truck,
                  );
                }
                return LpgGroupedList(
                  children: [
                    for (final trip in trips)
                      _TripTile(
                        trip: trip,
                        fleet: fleet,
                        onCancel: () => _cancelTrip(trip),
                      ),
                  ],
                );
              },
            ),
            const SizedBox(height: LpgSpacing.xxl),
          ],
        ),
      ),
    );
  }
}

/// One trip as a row of the trips list: van and driver, how far through its
/// stops it is, and the shortcut to cancel it while it has not left.
class _TripTile extends StatelessWidget {
  const _TripTile({
    required this.trip,
    required this.fleet,
    required this.onCancel,
  });

  final RouteSummary trip;
  final FleetData? fleet;
  final VoidCallback onCancel;

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;
    final total = trip.stops.length;
    final done = trip.stops.where((s) => s.status != 'pending').length;
    final severity = tripStatusSeverity(trip.status);
    final title = fleet == null
        ? 'Trip'
        : '${fleet!.vehicleName(trip.vehicleId)} · '
              '${fleet!.driverName(trip.driverId)}';

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        LpgListTile(
          leadingIcon: LpgIcons.truck,
          leadingTone: severity.tone,
          title: title,
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
        if (trip.status == 'planned' || trip.status == 'loaded')
          Align(
            alignment: Alignment.centerRight,
            child: Padding(
              padding: const EdgeInsets.only(right: LpgSpacing.sm),
              child: LpgButton(
                label: 'Cancel trip',
                variant: LpgButtonVariant.text,
                onPressed: onCancel,
              ),
            ),
          ),
      ],
    );
  }
}
