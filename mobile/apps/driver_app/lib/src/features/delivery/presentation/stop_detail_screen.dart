import 'package:api_client/api_client.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../offline/delivery_mutations.dart';
import '../../../offline/offline_banner.dart';
import '../../../offline/pending_sync.dart';
import '../data/active_route_provider.dart';
import '../data/stop_order_provider.dart';
import 'failed_delivery_sheet.dart';
import 'widgets/stop_map_card.dart';

/// One delivery stop: the order summary + the actions available at its
/// current status (depart, record delivery, mark failed).
class StopDetailScreen extends ConsumerWidget {
  const StopDetailScreen({super.key, required this.orderId});

  final String orderId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);
    final colors = theme.extension<LpgColors>()!;
    final orderAsync = ref.watch(stopOrderProvider(orderId));

    return Scaffold(
      appBar: AppBar(title: const Text('Delivery')),
      body: Column(
        children: [
          const OfflineBanner(),
          Expanded(child: _body(context, ref, theme, colors, orderAsync)),
        ],
      ),
    );
  }

  Widget _body(
    BuildContext context,
    WidgetRef ref,
    ThemeData theme,
    LpgColors colors,
    AsyncValue<OrderResponse> orderAsync,
  ) {
    return orderAsync.when(
      loading: () => const Center(child: LpgLoadingIndicator()),
      error: (err, _) => LpgEmptyState(
        message: 'Could not load this stop.\n$err',
        icon: Icons.error_outline,
        actionLabel: 'Retry',
        onAction: () => ref.invalidate(stopOrderProvider(orderId)),
      ),
      data: (order) {
        final cylinders = order.lines.fold<int>(
          0,
          (sum, l) => sum + l.quantityOrdered,
        );
        return ListView(
          padding: const EdgeInsets.all(16),
          children: [
            LpgCard(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text(
                        order.orderNumber ??
                            '#${order.id.substring(0, 8).toUpperCase()}',
                        style: theme.textTheme.titleMedium?.copyWith(
                          fontWeight: FontWeight.bold,
                          color: colors.textPrimary,
                        ),
                      ),
                      Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          if (ref
                                  .watch(pendingSyncAggregatesProvider)
                                  .value
                                  ?.contains(orderId) ??
                              false) ...[
                            const LpgStatusBadge(
                              label: 'PENDING SYNC',
                              severity: LpgStatusSeverity.info,
                            ),
                            const SizedBox(width: 8),
                          ],
                          LpgStatusBadge(
                            label: order.status
                                .replaceAll('_', ' ')
                                .toUpperCase(),
                            severity: _severity(order.status),
                          ),
                        ],
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  _DetailRow(
                    icon: Icons.location_on_outlined,
                    text: order.deliveryAddress.addressLine,
                  ),
                  const SizedBox(height: 8),
                  _DetailRow(
                    icon: Icons.propane_tank_outlined,
                    text: '$cylinders cylinder${cylinders == 1 ? '' : 's'}',
                  ),
                  if (order.totalAmount != null) ...[
                    const SizedBox(height: 8),
                    _DetailRow(
                      icon: Icons.payments_outlined,
                      text: 'Collect ₹${order.totalAmount!.toStringAsFixed(2)}',
                    ),
                  ],
                ],
              ),
            ),
            const SizedBox(height: 16),
            StopMapCard(orderId: order.id),
            const SizedBox(height: 24),
            ..._actions(context, ref, order),
          ],
        );
      },
    );
  }

  List<Widget> _actions(
    BuildContext context,
    WidgetRef ref,
    OrderResponse order,
  ) {
    switch (order.status) {
      case 'ready_for_dispatch' || 'assigned':
        return [
          LpgButton(
            label: 'Start this delivery',
            expand: true,
            onPressed: () => _run(
              context,
              ref,
              () => ref.read(deliveryMutationsProvider).departStop(order.id),
              doneMessage: 'Delivery started.',
            ),
          ),
        ];
      case 'out_for_delivery':
        return [
          LpgButton(
            label: 'Record delivery',
            expand: true,
            icon: Icons.check_circle_outline,
            onPressed: () => context.pushNamed(
              'deliver',
              pathParameters: {'orderId': order.id},
            ),
          ),
          const SizedBox(height: 12),
          LpgButton(
            label: 'Delivery failed',
            variant: LpgButtonVariant.secondary,
            expand: true,
            onPressed: () => _openFailedSheet(context, ref, order.id),
          ),
        ];
      default:
        return [
          LpgEmptyState(
            message:
                'Nothing to do here — this stop is '
                '${order.status.replaceAll('_', ' ')}.',
            icon: Icons.done_all,
          ),
        ];
    }
  }

  Future<void> _openFailedSheet(
    BuildContext context,
    WidgetRef ref,
    String id,
  ) async {
    final choice =
        await showModalBottomSheet<({String reason, String? action})>(
          context: context,
          showDragHandle: true,
          isScrollControlled: true,
          builder: (_) => const FailedDeliverySheet(),
        );
    if (choice == null || !context.mounted) return;
    await _run(
      context,
      ref,
      () => ref
          .read(deliveryMutationsProvider)
          .recordFailedDelivery(
            id,
            reasonCode: choice.reason,
            resolutionAction: choice.action,
          ),
      doneMessage: 'Marked as failed.',
    );
  }

  /// Runs a queued mutation: it moves the local state now and drains to the
  /// backend in the background, so "done" here means "recorded and queued",
  /// not "the server has confirmed it". A genuine rejection surfaces later on
  /// the sync-status screen.
  Future<void> _run(
    BuildContext context,
    WidgetRef ref,
    Future<void> Function() action, {
    required String doneMessage,
  }) async {
    final messenger = ScaffoldMessenger.of(context);
    try {
      await action();
    } catch (e) {
      if (!context.mounted) return;
      messenger.showSnackBar(
        SnackBar(content: Text("Couldn't queue that: $e")),
      );
      return;
    }
    if (!context.mounted) return;
    ref.invalidate(stopOrderProvider(orderId));
    ref.invalidate(activeRouteProvider);
    messenger.showSnackBar(SnackBar(content: Text(doneMessage)));
  }

  LpgStatusSeverity _severity(String status) => switch (status) {
    'delivered' => LpgStatusSeverity.success,
    'failed_delivery' || 'cancelled' => LpgStatusSeverity.danger,
    'out_for_delivery' => LpgStatusSeverity.warning,
    _ => LpgStatusSeverity.info,
  };
}

class _DetailRow extends StatelessWidget {
  const _DetailRow({required this.icon, required this.text});

  final IconData icon;
  final String text;

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).extension<LpgColors>()!;
    final theme = Theme.of(context);
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(icon, size: 18, color: colors.textSecondary),
        const SizedBox(width: 12),
        Expanded(
          child: Text(
            text,
            style: theme.textTheme.bodyMedium?.copyWith(
              color: colors.textPrimary,
            ),
          ),
        ),
      ],
    );
  }
}
