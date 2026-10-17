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
        padding: const EdgeInsets.all(LpgSpacing.xxl),
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
      LpgFeedback.showToast(
        context,
        'No maps app available.',
        tone: LpgTone.warning,
      );
    }
  }

  /// Tall enough to read the streets around the pin at a glance in a cab
  /// mount, short enough to keep the actions above the fold.
  static const _mapHeight = LpgSizes.avatarLg * 3.5;

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;
    final destinationAsync = ref.watch(stopDestinationProvider(widget.orderId));
    final driver = ref.watch(driverPositionProvider).value;

    return destinationAsync.when(
      loading: () => const LpgCard(
        padding: EdgeInsets.zero,
        child: SizedBox(
          height: _mapHeight,
          child: LpgShimmer(child: LpgSkeleton(height: _mapHeight)),
        ),
      ),
      error: (_, _) => const LpgCard(
        padding: EdgeInsets.zero,
        child: SizedBox(
          height: _mapHeight,
          child: MapUnavailable(message: 'Could not load the map.'),
        ),
      ),
      data: (destination) {
        final point = destination.point;
        if (point == null) {
          return const LpgCard(
            padding: EdgeInsets.zero,
            child: SizedBox(
              height: _mapHeight,
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
                  top: Radius.circular(LpgRadius.xl),
                ),
                child: SizedBox(
                  height: _mapHeight,
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
                        const Positioned(
                          top: LpgSpacing.sm,
                          left: LpgSpacing.sm,
                          right: LpgSpacing.sm,
                          child: _ApproximateBanner(),
                        ),
                      Positioned(
                        right: LpgSpacing.sm,
                        bottom: LpgSpacing.sm,
                        child: IconButton.filledTonal(
                          tooltip: 'Recenter map',
                          onPressed: () => _recenter(point, driver),
                          icon: const Icon(LpgIcons.recenter),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              Padding(
                padding: const EdgeInsets.all(LpgSpacing.smd),
                child: LpgButton(
                  label: 'Navigate',
                  icon: LpgIcons.navigate,
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
  const _ApproximateBanner();

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;
    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: LpgSpacing.smd,
        vertical: LpgSpacing.sm,
      ),
      decoration: BoxDecoration(
        color: colors.card.withValues(alpha: 0.95),
        borderRadius: BorderRadius.circular(LpgRadius.lg),
        border: Border.all(color: colors.borderDefault),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(LpgIcons.info, size: LpgSizes.iconSm, color: colors.statusInfo),
          const SizedBox(width: LpgSpacing.sm),
          Flexible(
            child: Text(
              'Approximate location, from the delivery address.',
              style: context.lpgText.bodySmall?.copyWith(
                color: colors.textPrimary,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
