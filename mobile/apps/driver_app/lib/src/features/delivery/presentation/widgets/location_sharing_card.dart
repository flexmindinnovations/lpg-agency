import 'package:api_client/api_client.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../data/location_sharing.dart';

/// The "Share live location" card — a switch that starts/stops reporting the
/// driver's position for the active route. Shown on the Today tab; the
/// controller it drives outlives every screen (session-scoped provider).
class LocationSharingCard extends ConsumerWidget {
  const LocationSharingCard({super.key, required this.route});

  final RouteSummary route;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);
    final colors = theme.extension<LpgColors>()!;
    final sharingState = ref.watch(locationSharingStateProvider).value;
    final controller = ref.read(locationSharingControllerProvider);

    final canShare = route.isInProgress;
    final isSharing = sharingState?.isSharing ?? false;

    final subtitle = switch (sharingState?.status) {
      LocationSharingStatus.permissionBlocked =>
        sharingState?.message ?? 'Location permission is off.',
      LocationSharingStatus.error => sharingState?.message ?? 'Sharing error.',
      _ when !canShare => 'Available once you depart with the vehicle.',
      _ when isSharing && sharingState?.lastSentAt != null =>
        'Customers can see your location, even in the background. '
            'Last update ${_ago(sharingState!.lastSentAt!)}.',
      _ when isSharing =>
        'Customers can see your location, even in the background.',
      _ => 'Let customers track their delivery on the map.',
    };

    return LpgCard(
      child: Row(
        children: [
          Icon(
            isSharing ? Icons.my_location : Icons.location_disabled,
            color: isSharing ? colors.statusInfo : colors.textSecondary,
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Share live location',
                  style: theme.textTheme.titleSmall?.copyWith(
                    fontWeight: FontWeight.w600,
                    color: colors.textPrimary,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  subtitle,
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: colors.textSecondary,
                  ),
                ),
              ],
            ),
          ),
          Switch(
            value: isSharing,
            onChanged: canShare
                ? (on) {
                    if (on) {
                      controller.start(route.id);
                    } else {
                      controller.stop();
                    }
                  }
                : null,
          ),
        ],
      ),
    );
  }

  String _ago(DateTime at) {
    final seconds = DateTime.now().difference(at).inSeconds;
    if (seconds < 60) return '${seconds}s ago';
    return '${seconds ~/ 60}m ago';
  }
}
