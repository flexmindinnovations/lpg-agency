import 'package:api_client/api_client.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../offline/pending_sync.dart';

/// One row of an `LpgGroupedList` for a stop on the route: order ref and
/// status, tappable through to the stop detail. Shared by the Today "next stop" card and the
/// Deliveries list. Shows a "pending sync" hint while this stop's last
/// action is still queued.
class StopTile extends ConsumerWidget {
  const StopTile({super.key, required this.stop, this.onTap});

  final RouteStopSummary stop;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final pending =
        ref
            .watch(pendingSyncAggregatesProvider)
            .value
            ?.contains(stop.orderId) ??
        false;

    final (IconData icon, LpgTone tone) = switch (stop.status) {
      'delivered' => (LpgIcons.success, LpgTone.success),
      'failed' => (LpgIcons.cancel, LpgTone.danger),
      'en_route' => (LpgIcons.navigate, LpgTone.accent),
      'cancelled' => (LpgIcons.blocked, LpgTone.neutral),
      _ => (LpgIcons.location, LpgTone.primary),
    };

    return LpgListTile(
      leadingIcon: icon,
      leadingTone: tone,
      title: 'Order ${LpgFormat.orderNumber(stop.orderNumber, stop.orderId)}',
      subtitle:
          'Stop ${stop.sequenceNumber}  ·  ${LpgFormat.statusLabel(stop.status)}',
      trailing: pending
          ? const LpgStatusBadge(
              label: 'PENDING SYNC',
              severity: LpgStatusSeverity.info,
              icon: LpgIcons.upload,
            )
          : null,
      showChevron: onTap != null && !pending,
      onTap: onTap,
    );
  }
}
