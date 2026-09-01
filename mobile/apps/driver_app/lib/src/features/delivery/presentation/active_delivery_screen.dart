import 'package:api_client/api_client.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../data/active_route_provider.dart';
import '../data/location_sharing.dart';

/// The Driver App's home: the active route, its stops, and a switch to share
/// live location with customers while the route is in progress.
class ActiveDeliveryScreen extends ConsumerWidget {
  const ActiveDeliveryScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);
    final colors = theme.extension<LpgColors>()!;
    final routeAsync = ref.watch(activeRouteProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Today’s Deliveries')),
      body: RefreshIndicator(
        onRefresh: () => ref.refresh(activeRouteProvider.future),
        child: routeAsync.when(
          loading: () => const Center(child: LpgLoadingIndicator()),
          error: (err, _) => ListView(
            children: [
              LpgEmptyState(
                message: 'Could not load your route.\n$err',
                icon: Icons.error_outline,
                actionLabel: 'Retry',
                onAction: () => ref.invalidate(activeRouteProvider),
              ),
            ],
          ),
          data: (route) {
            if (route == null) {
              return ListView(
                children: const [
                  SizedBox(height: 120),
                  LpgEmptyState(
                    message: 'No active route right now.',
                    icon: Icons.local_shipping_outlined,
                  ),
                ],
              );
            }
            return ListView(
              padding: const EdgeInsets.all(16),
              children: [
                _RouteHeader(route: route),
                const SizedBox(height: 16),
                _LocationSharingCard(route: route),
                const SizedBox(height: 24),
                Text(
                  'Stops',
                  style: theme.textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.w600,
                    color: colors.textPrimary,
                  ),
                ),
                const SizedBox(height: 8),
                for (final stop in route.stops)
                  _StopTile(
                    stop: stop,
                    onTap: () => context.pushNamed(
                      'stop',
                      pathParameters: {'orderId': stop.orderId},
                    ),
                  ),
              ],
            );
          },
        ),
      ),
    );
  }
}

class _RouteHeader extends StatelessWidget {
  const _RouteHeader({required this.route});

  final RouteSummary route;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colors = theme.extension<LpgColors>()!;
    return LpgCard(
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Route',
                style: theme.textTheme.labelSmall?.copyWith(
                  color: colors.textSecondary,
                ),
              ),
              Text(
                route.status.replaceAll('_', ' ').toUpperCase(),
                style: theme.textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.bold,
                  color: colors.textPrimary,
                ),
              ),
            ],
          ),
          Text(
            '${route.stops.length} stop${route.stops.length == 1 ? '' : 's'}',
            style: theme.textTheme.bodyMedium?.copyWith(
              color: colors.textSecondary,
            ),
          ),
        ],
      ),
    );
  }
}

class _LocationSharingCard extends ConsumerWidget {
  const _LocationSharingCard({required this.route});

  final RouteSummary route;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);
    final colors = theme.extension<LpgColors>()!;
    final sharingState = ref
        .watch(locationSharingStateProvider)
        .value;
    final controller = ref.read(locationSharingControllerProvider);

    final canShare = route.isInProgress;
    final isSharing = sharingState?.isSharing ?? false;

    final subtitle = switch (sharingState?.status) {
      LocationSharingStatus.permissionBlocked =>
        sharingState?.message ?? 'Location permission is off.',
      LocationSharingStatus.error => sharingState?.message ?? 'Sharing error.',
      _ when !canShare =>
        'Available once you depart with the vehicle.',
      _ when isSharing && sharingState?.lastSentAt != null =>
        'Customers can see your location. Last update '
            '${_ago(sharingState!.lastSentAt!)}.',
      _ when isSharing => 'Customers can see your location.',
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

class _StopTile extends StatelessWidget {
  const _StopTile({required this.stop, this.onTap});

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
