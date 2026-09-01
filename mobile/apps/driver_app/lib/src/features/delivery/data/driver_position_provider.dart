import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:geolocator/geolocator.dart';
import 'package:maps/maps.dart';

import 'location_sharing.dart';

/// The driver's current position for the stop-detail map — best-effort:
/// `null` on a denied permission or any plugin error, so the map still
/// renders (just without the "you are here" marker).
final driverPositionProvider = FutureProvider.autoDispose<LatLng?>((ref) async {
  try {
    final geolocator = ref.watch(driverGeolocatorProvider);
    final permission = await geolocator.ensurePermission();
    if (permission == LocationPermission.denied ||
        permission == LocationPermission.deniedForever) {
      return null;
    }
    final position = await geolocator.currentPosition();
    return LatLng(position.latitude, position.longitude);
  } catch (_) {
    return null;
  }
});
