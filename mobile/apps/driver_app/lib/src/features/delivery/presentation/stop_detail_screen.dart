import 'package:api_client/api_client.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../offline/delivery_mutations.dart';
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
    final orderAsync = ref.watch(stopOrderProvider(orderId));

    return Scaffold(
      appBar: AppBar(title: const Text('Delivery')),
      // The shell (this screen now lives under the Deliveries branch) owns
      // the offline banner and the bottom bar.
      body: orderAsync.when(
        loading: () => const LpgSkeletonList(itemCount: 3),
        error: (err, _) => LpgErrorState(
          message: 'Could not load this stop.\n$err',
          onRetry: () => ref.invalidate(stopOrderProvider(orderId)),
        ),
        data: (order) {
          final pendingSync =
              ref
                  .watch(pendingSyncAggregatesProvider)
                  .value
                  ?.contains(orderId) ??
              false;
          final children = [
            _SummaryCard(order: order, pendingSync: pendingSync),
            StopMapCard(orderId: order.id),
            Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: _actions(context, ref, order),
            ),
          ];
          return ListView.separated(
            padding: LpgSpacing.page,
            itemCount: children.length,
            separatorBuilder: (_, _) => const SizedBox(height: LpgSpacing.md),
            itemBuilder: (context, i) =>
                LpgFadeSlideIn(index: i, child: children[i]),
          );
        },
      ),
    );
  }

  List<Widget> _actions(
    BuildContext context,
    WidgetRef ref,
    OrderResponse order,
  ) {
    // The backend refuses to start, deliver or fail a stop until the office
    // has loaded the van; say so here rather than letting the action bounce.
    final vanNotLoaded =
        ref.watch(stopRouteStatusProvider(order.id)) == 'planned';
    switch (order.status) {
      case 'assigned' || 'ready_for_dispatch' || 'out_for_delivery'
          when vanNotLoaded:
        return [
          LpgBanner(
            tone: LpgTone.warning,
            icon: LpgIcons.cylinder,
            title: 'Van not loaded yet',
            message:
                'The office hasn\'t finished loading your van for this route. '
                'You can start this delivery once loading is complete.',
            actionLabel: 'Check again',
            onAction: () => ref.invalidate(activeRouteProvider),
          ),
        ];
      case 'assigned':
        return [
          LpgBanner(
            tone: LpgTone.info,
            icon: LpgIcons.info,
            title: 'Waiting for dispatch',
            message:
                'The office hasn\'t marked this order ready for dispatch yet. '
                'You can start it once they do.',
            actionLabel: 'Check again',
            onAction: () => ref.invalidate(stopOrderProvider(orderId)),
          ),
        ];
      case 'ready_for_dispatch':
        return [
          LpgButton(
            label: 'Start this delivery',
            icon: LpgIcons.navigate,
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
            icon: LpgIcons.check,
            onPressed: () => context.goNamed(
              'deliver',
              pathParameters: {'orderId': order.id},
            ),
          ),
          const SizedBox(height: LpgSpacing.smd),
          LpgButton(
            label: 'Delivery failed',
            icon: LpgIcons.cancel,
            variant: LpgButtonVariant.secondary,
            expand: true,
            onPressed: () => _openFailedSheet(context, ref, order.id),
          ),
        ];
      default:
        return [
          LpgBanner(
            tone: _severity(order.status).tone,
            icon: LpgIcons.allDone,
            message:
                'Nothing to do here — this stop is '
                '${LpgFormat.sentence(order.status).toLowerCase()}.',
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
    try {
      await action();
    } catch (e) {
      if (!context.mounted) return;
      LpgFeedback.showToast(
        context,
        "Couldn't queue that: $e",
        tone: LpgTone.danger,
      );
      return;
    }
    if (!context.mounted) return;
    ref.invalidate(stopOrderProvider(orderId));
    ref.invalidate(activeRouteProvider);
    LpgFeedback.showToast(context, doneMessage, tone: LpgTone.success);
  }

  static LpgStatusSeverity _severity(String status) => switch (status) {
    'delivered' => LpgStatusSeverity.success,
    'failed_delivery' || 'cancelled' => LpgStatusSeverity.danger,
    'out_for_delivery' => LpgStatusSeverity.warning,
    _ => LpgStatusSeverity.info,
  };
}

/// Order number, status, address, cylinders and the amount to collect.
class _SummaryCard extends StatelessWidget {
  const _SummaryCard({required this.order, required this.pendingSync});

  final OrderResponse order;
  final bool pendingSync;

  @override
  Widget build(BuildContext context) {
    final cylinders = order.lines.fold<int>(
      0,
      (sum, l) => sum + l.quantityOrdered,
    );
    return LpgCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  LpgFormat.orderNumber(order.orderNumber, order.id),
                  style: context.lpgText.titleLarge,
                ),
              ),
              if (pendingSync) ...[
                const LpgStatusBadge(
                  label: 'PENDING SYNC',
                  severity: LpgStatusSeverity.info,
                  icon: LpgIcons.sync,
                ),
                const SizedBox(width: LpgSpacing.sm),
              ],
              LpgStatusBadge(
                label: LpgFormat.statusLabel(order.status),
                severity: StopDetailScreen._severity(order.status),
              ),
            ],
          ),
          const Divider(height: LpgSpacing.xl),
          _DetailRow(
            icon: LpgIcons.location,
            text: order.deliveryAddress.addressLine,
          ),
          const SizedBox(height: LpgSpacing.smd),
          _DetailRow(
            icon: LpgIcons.cylinder,
            text: '$cylinders cylinder${cylinders == 1 ? '' : 's'}',
          ),
          if (order.totalAmount != null) ...[
            const SizedBox(height: LpgSpacing.smd),
            _DetailRow(
              icon: LpgIcons.cash,
              tone: LpgTone.accent,
              text: 'Collect ${LpgFormat.currency(order.totalAmount!)}',
            ),
          ],
        ],
      ),
    );
  }
}

class _DetailRow extends StatelessWidget {
  const _DetailRow({
    required this.icon,
    required this.text,
    this.tone = LpgTone.neutral,
  });

  final IconData icon;
  final String text;
  final LpgTone tone;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        LpgIconBox(icon: icon, tone: tone, size: LpgSizes.avatarSm),
        const SizedBox(width: LpgSpacing.smd),
        Expanded(child: Text(text, style: context.lpgText.bodyLarge)),
      ],
    );
  }
}
