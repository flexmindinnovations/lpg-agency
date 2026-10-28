import 'package:api_client/api_client.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../api_result.dart';
import '../../orders/data/orders_provider.dart';
import '../../orders/presentation/sheets/send_out_sheet.dart';
import '../data/dispatch_provider.dart';
import '../domain/trip_status.dart';

/// The trip sheet: confirmed orders waiting for a van, and the trips that
/// are loading or out. "Send out" opens the same sheet as the order page
/// (pick a driver and van, load, hand over in one step).
class DispatchScreen extends ConsumerWidget {
  const DispatchScreen({super.key});

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
    ref.invalidate(ordersWaitingForTripProvider);
    ref.invalidate(adminOrdersProvider);
    ref.invalidate(activeTripsProvider);
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final colors = context.lpgColors;
    final text = context.lpgText;
    final tripsAsync = ref.watch(dispatchTripsProvider);
    final waitingAsync = ref.watch(ordersWaitingForTripProvider);
    final fleet = ref.watch(fleetProvider).value;
    final names = ref.watch(cylinderNamesProvider).value ?? const {};

    return Scaffold(
      appBar: AppBar(
        title: const Text('Dispatch'),
        actions: [
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
          await ref.read(dispatchTripsProvider.future);
        },
        child: ListView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: LpgSpacing.page,
          children: [
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
                return Column(
                  children: [
                    for (final order in orders) ...[
                      LpgCard(
                        onTap: () => context.goNamed(
                          'order_detail',
                          pathParameters: {'orderId': order.id},
                        ),
                        child: Row(
                          children: [
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    LpgFormat.orderNumber(
                                      order.orderNumber,
                                      order.id,
                                    ),
                                    style: text.titleSmall,
                                  ),
                                  Text(
                                    order.customerName ?? 'Customer',
                                    style: text.bodyMedium?.copyWith(
                                      color: colors.textSecondary,
                                    ),
                                  ),
                                  Text(
                                    [
                                      for (final l in order.lines)
                                        '${l.quantityOrdered} × '
                                            '${names[l.cylinderTypeId] ?? 'Cylinder'}',
                                    ].join(', '),
                                    style: text.bodySmall?.copyWith(
                                      color: colors.textSecondary,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                            LpgButton(
                              label: 'Send out',
                              icon: LpgIcons.truck,
                              variant: LpgButtonVariant.tonal,
                              onPressed: () => _sendOut(context, ref, order),
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(height: LpgSpacing.sm),
                    ],
                  ],
                );
              },
            ),
            const SizedBox(height: LpgSpacing.lg),
            Text('Trips', style: text.titleMedium),
            const SizedBox(height: LpgSpacing.sm),
            tripsAsync.when(
              loading: () => const LpgSkeletonList(itemCount: 3),
              error: (err, _) => LpgErrorState(
                message: errorMessage(err),
                onRetry: () => ref.invalidate(dispatchTripsProvider),
              ),
              data: (trips) {
                if (trips.isEmpty) {
                  return const LpgEmptyState(
                    message: 'No trips are loading or on the road.',
                    icon: LpgIcons.truck,
                  );
                }
                return Column(
                  children: [
                    for (final trip in trips) ...[
                      LpgCard(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              mainAxisAlignment: MainAxisAlignment.spaceBetween,
                              children: [
                                Expanded(
                                  child: Text(
                                    fleet == null
                                        ? 'Trip'
                                        : '${fleet.driverName(trip.driverId)} · '
                                              '${fleet.vehicleName(trip.vehicleId)}',
                                    style: text.titleSmall,
                                  ),
                                ),
                                LpgStatusBadge(
                                  label: tripStatusLabel(trip.status),
                                  severity: tripStatusSeverity(trip.status),
                                ),
                              ],
                            ),
                            const SizedBox(height: LpgSpacing.xs),
                            if (trip.stops.isEmpty)
                              Text(
                                'No orders on this trip yet.',
                                style: text.bodySmall?.copyWith(
                                  color: colors.textSecondary,
                                ),
                              ),
                            for (final stop in trip.stops)
                              InkWell(
                                onTap: () => context.goNamed(
                                  'order_detail',
                                  pathParameters: {'orderId': stop.orderId},
                                ),
                                child: Padding(
                                  padding: const EdgeInsets.symmetric(
                                    vertical: LpgSpacing.xs,
                                  ),
                                  child: Row(
                                    mainAxisAlignment:
                                        MainAxisAlignment.spaceBetween,
                                    children: [
                                      Text(
                                        LpgFormat.orderNumber(
                                          stop.orderNumber,
                                          stop.orderId,
                                        ),
                                        style: text.bodyMedium,
                                      ),
                                      Text(
                                        LpgFormat.statusLabel(stop.status),
                                        style: text.bodySmall?.copyWith(
                                          color: colors.textSecondary,
                                        ),
                                      ),
                                    ],
                                  ),
                                ),
                              ),
                          ],
                        ),
                      ),
                      const SizedBox(height: LpgSpacing.sm),
                    ],
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
