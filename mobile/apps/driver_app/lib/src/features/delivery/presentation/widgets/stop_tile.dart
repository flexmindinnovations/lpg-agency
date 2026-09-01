import 'package:api_client/api_client.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';

/// One row in the route's stop list — order ref + status, tappable through
/// to the stop detail. Shared by the Today "next stop" card and the
/// Deliveries list.
class StopTile extends StatelessWidget {
  const StopTile({super.key, required this.stop, this.onTap});

  final RouteStopSummary stop;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final done = stop.status == 'delivered' || stop.status == 'failed';
    return LpgCard(
      padding: EdgeInsets.zero,
      onTap: onTap,
      child: LpgListTile(
        leadingIcon: done ? Icons.check_circle_outline : Icons.circle_outlined,
        title: 'Stop ${stop.sequenceNumber + 1}',
        subtitle: 'Order ${stop.orderId.substring(0, 8).toUpperCase()}',
        trailing: Text(stop.status.replaceAll('_', ' ')),
      ),
    );
  }
}
