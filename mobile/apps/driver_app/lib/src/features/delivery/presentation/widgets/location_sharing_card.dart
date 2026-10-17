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
    final colors = context.lpgColors;
    final text = context.lpgText;
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

    final blocked =
        sharingState?.status == LocationSharingStatus.permissionBlocked ||
        sharingState?.status == LocationSharingStatus.error;

    return LpgCard(
      variant: isSharing ? LpgCardVariant.tonal : LpgCardVariant.elevated,
      tone: LpgTone.info,
      child: Row(
        children: [
          LpgIconBox(
            icon: isSharing ? LpgIcons.myLocation : LpgIcons.locationOff,
            tone: blocked
                ? LpgTone.danger
                : isSharing
                ? LpgTone.info
                : LpgTone.neutral,
          ),
          const SizedBox(width: LpgSpacing.md),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Share live location',
                  style: text.titleSmall?.copyWith(color: colors.textPrimary),
                ),
                const SizedBox(height: LpgSpacing.xs / 2),
                Text(
                  subtitle,
                  style: text.bodySmall?.copyWith(
                    color: blocked ? colors.statusDanger : colors.textSecondary,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(width: LpgSpacing.sm),
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
