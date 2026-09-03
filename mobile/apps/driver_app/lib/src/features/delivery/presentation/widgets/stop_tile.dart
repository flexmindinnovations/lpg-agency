import 'package:api_client/api_client.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../offline/pending_sync.dart';

/// One row in the route's stop list — order ref + status, tappable through
/// to the stop detail. Shared by the Today "next stop" card and the
/// Deliveries list. Shows a "pending sync" hint while this stop's last
/// action is still queued.
class StopTile extends ConsumerWidget {
  const StopTile({super.key, required this.stop, this.onTap});

  final RouteStopSummary stop;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final done = stop.status == 'delivered' || stop.status == 'failed';
    final pending =
        ref
            .watch(pendingSyncAggregatesProvider)
            .value
            ?.contains(stop.orderId) ??
        false;

    return LpgCard(
      padding: EdgeInsets.zero,
      onTap: onTap,
      child: LpgListTile(
        leadingIcon: done ? Icons.check_circle_outline : Icons.circle_outlined,
        title: 'Stop ${stop.sequenceNumber}',
        subtitle: 'Order ${stop.orderId.substring(0, 8).toUpperCase()}',
        trailing: pending
            ? const LpgStatusBadge(
                label: 'PENDING SYNC',
                severity: LpgStatusSeverity.info,
              )
            : Text(stop.status.replaceAll('_', ' ')),
      ),
    );
  }
}
