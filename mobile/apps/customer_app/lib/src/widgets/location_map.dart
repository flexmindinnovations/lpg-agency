import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';

/// OpenStreetMap tile URL. `tile.openstreetmap.org` is the round-robin CDN
/// endpoint the OSM tile-usage policy points third parties at.
const _osmTileUrl = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';

/// The app's identifier, sent as the tile requests' `User-Agent` per the OSM
/// tile-usage policy.
const _userAgent = 'com.lpgagency.customer_app';

/// A small non-interactive-by-default OSM map with a set of markers.
///
/// [tileProvider] is injectable so widget tests can supply a provider that
/// doesn't hit the network.
class LocationMap extends StatelessWidget {
  const LocationMap({
    super.key,
    required this.center,
    this.markers = const [],
    this.zoom = 15,
    this.mapController,
    this.interactive = false,
    this.onTap,
    this.tileProvider,
  });

  final LatLng center;
  final List<Marker> markers;
  final double zoom;
  final MapController? mapController;
  final bool interactive;
  final void Function(LatLng point)? onTap;
  final TileProvider? tileProvider;

  @override
  Widget build(BuildContext context) {
    return FlutterMap(
      mapController: mapController,
      options: MapOptions(
        initialCenter: center,
        initialZoom: zoom,
        onTap: onTap == null ? null : (_, point) => onTap!(point),
        interactionOptions: InteractionOptions(
          flags: interactive
              ? InteractiveFlag.all & ~InteractiveFlag.rotate
              : InteractiveFlag.none,
        ),
      ),
      children: [
        TileLayer(
          urlTemplate: _osmTileUrl,
          userAgentPackageName: _userAgent,
          tileProvider: tileProvider,
        ),
        if (markers.isNotEmpty) MarkerLayer(markers: markers),
        const RichAttributionWidget(
          alignment: AttributionAlignment.bottomLeft,
          attributions: [
            TextSourceAttribution('© OpenStreetMap contributors'),
          ],
        ),
      ],
    );
  }
}

/// A teardrop pin marker in the given [color].
Marker pinMarker({
  required LatLng point,
  required Color color,
  IconData icon = Icons.location_on,
  double size = 40,
}) {
  return Marker(
    point: point,
    width: size,
    height: size,
    alignment: Alignment.topCenter,
    child: Icon(icon, color: color, size: size),
  );
}

/// A circular "vehicle" marker for the driver's live position.
Marker driverMarker({required LatLng point, required Color color}) {
  return Marker(
    point: point,
    width: 44,
    height: 44,
    child: DecoratedBox(
      decoration: BoxDecoration(
        color: color,
        shape: BoxShape.circle,
        boxShadow: [
          BoxShadow(
            color: color.withValues(alpha: 0.35),
            blurRadius: 12,
            spreadRadius: 4,
          ),
        ],
      ),
      child: const Icon(Icons.local_shipping, color: Colors.white, size: 22),
    ),
  );
}

/// Placeholder shown when there is no location to plot.
class MapUnavailable extends StatelessWidget {
  const MapUnavailable({super.key, required this.message});

  final String message;

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).extension<LpgColors>()!;
    final theme = Theme.of(context);
    return ColoredBox(
      color: colors.surfaceOverlay,
      child: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              Icons.map_outlined,
              size: 64,
              color: colors.textSecondary.withValues(alpha: 0.3),
            ),
            const SizedBox(height: 16),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 32),
              child: Text(
                message,
                textAlign: TextAlign.center,
                style: theme.textTheme.bodyMedium?.copyWith(
                  color: colors.textSecondary,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
