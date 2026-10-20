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

    return LpgCard(
      padding: EdgeInsets.zero,
      onTap: onTap,
      child: LpgListTile(
        leadingIcon: icon,
        leadingTone: tone,
        title: 'Stop ${stop.sequenceNumber}',
        subtitle:
            'Order ${LpgFormat.orderNumber(stop.orderNumber, stop.orderId)}',
        trailing: pending
            ? const LpgStatusBadge(
                label: 'PENDING SYNC',
                severity: LpgStatusSeverity.info,
                icon: LpgIcons.upload,
              )
            : LpgStatusBadge(
                label: LpgFormat.statusLabel(stop.status),
                severity: switch (stop.status) {
                  'delivered' => LpgStatusSeverity.success,
                  'failed' => LpgStatusSeverity.danger,
                  'en_route' => LpgStatusSeverity.warning,
                  _ => LpgStatusSeverity.neutral,
                },
              ),
        showChevron: onTap != null,
      ),
    );
  }
}
