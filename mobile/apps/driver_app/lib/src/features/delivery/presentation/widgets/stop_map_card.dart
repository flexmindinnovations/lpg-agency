import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:maps/maps.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../data/driver_position_provider.dart';
import '../../data/stop_destination_provider.dart';

/// The stop-detail route map: the delivery destination + the driver's own
/// position, with a recenter control and a "Navigate" button that opens the
/// device's maps app for turn-by-turn.
class StopMapCard extends ConsumerStatefulWidget {
  const StopMapCard({super.key, required this.orderId});

  final String orderId;

  @override
  ConsumerState<StopMapCard> createState() => _StopMapCardState();
}

class _StopMapCardState extends ConsumerState<StopMapCard> {
  final _mapController = MapController();

  @override
  void dispose() {
    _mapController.dispose();
    super.dispose();
  }

  void _recenter(LatLng destination, LatLng? driver) {
    if (driver == null) {
      _mapController.move(destination, 15);
      return;
    }
    _mapController.fitCamera(
      CameraFit.bounds(
        bounds: LatLngBounds(destination, driver),
        padding: const EdgeInsets.all(48),
      ),
    );
  }

  Future<void> _navigate(LatLng point) async {
    final lat = point.latitude;
    final lng = point.longitude;
    final candidates = [
      Uri.parse('google.navigation:q=$lat,$lng'),
      Uri.parse('https://maps.apple.com/?daddr=$lat,$lng'),
      Uri.parse('https://www.google.com/maps/dir/?api=1&destination=$lat,$lng'),
    ];
    for (final uri in candidates) {
      if (await launchUrl(uri, mode: LaunchMode.externalApplication)) return;
    }
    if (mounted) {
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(const SnackBar(content: Text('No maps app available.')));
    }
  }

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).extension<LpgColors>()!;
    final destinationAsync = ref.watch(stopDestinationProvider(widget.orderId));
    final driver = ref.watch(driverPositionProvider).value;

    return destinationAsync.when(
      loading: () => const LpgCard(
        child: SizedBox(
          height: 200,
          child: Center(child: LpgLoadingIndicator()),
        ),
      ),
      error: (_, _) => const LpgCard(
        child: SizedBox(
          height: 200,
          child: MapUnavailable(message: 'Could not load the map.'),
        ),
      ),
      data: (destination) {
        final point = destination.point;
        if (point == null) {
          return const LpgCard(
            padding: EdgeInsets.zero,
            child: SizedBox(
              height: 200,
              child: MapUnavailable(message: 'Delivery location not pinned.'),
            ),
          );
        }
        return LpgCard(
          padding: EdgeInsets.zero,
          child: Column(
            children: [
              ClipRRect(
                borderRadius: const BorderRadius.vertical(
                  top: Radius.circular(12),
                ),
                child: SizedBox(
                  height: 200,
                  child: Stack(
                    children: [
                      Positioned.fill(
                        child: LocationMap(
                          mapController: _mapController,
                          center: point,
                          interactive: true,
                          tileProvider: ref.watch(mapTileProviderProvider),
                          markers: [
                            pinMarker(
                              point: point,
                              color: colors.actionPrimary,
                            ),
                            if (driver != null)
                              driverMarker(
                                point: driver,
                                color: colors.statusInfo,
                              ),
                          ],
                        ),
                      ),
                      if (destination.isApproximate)
                        Positioned(
                          top: 8,
                          left: 8,
                          right: 8,
                          child: _ApproximateBanner(),
                        ),
                      Positioned(
                        right: 8,
                        bottom: 8,
                        child: FloatingActionButton.small(
                          heroTag: 'stop-map-recenter',
                          onPressed: () => _recenter(point, driver),
                          child: const Icon(Icons.center_focus_strong),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              Padding(
                padding: const EdgeInsets.all(12),
                child: LpgButton(
                  label: 'Navigate',
                  icon: Icons.navigation_outlined,
                  expand: true,
                  onPressed: () => _navigate(point),
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}

class _ApproximateBanner extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).extension<LpgColors>()!;
    final theme = Theme.of(context);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: colors.surfaceRaised.withValues(alpha: 0.95),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.info_outline, size: 16, color: colors.textSecondary),
          const SizedBox(width: 8),
          Flexible(
            child: Text(
              'Approximate location, from the delivery address.',
              style: theme.textTheme.labelSmall?.copyWith(
                color: colors.textSecondary,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
