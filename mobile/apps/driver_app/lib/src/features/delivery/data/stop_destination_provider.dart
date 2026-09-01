import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:maps/maps.dart';

import 'stop_order_provider.dart';

/// The delivery location for one stop, for the stop-detail map.
class StopDestination {
  const StopDestination({
    required this.point,
    required this.label,
    required this.isApproximate,
  });

  /// `null` when the order carried no pin and geocoding the address failed.
  final LatLng? point;
  final String label;

  /// `true` when [point] came from geocoding the address text, not a pin —
  /// show it as "approximate".
  final bool isApproximate;
}

/// Resolves a stop's destination: the order's pinned coords when present,
/// else a LocationIQ/Nominatim geocode of the free-text address. Mirrors the
/// customer app's `orderTrackingProvider` fallback. `autoDispose` releases
/// the geocode cache when the stop screen closes.
final stopDestinationProvider = FutureProvider.autoDispose
    .family<StopDestination, String>((ref, orderId) async {
      final order = await ref.watch(stopOrderProvider(orderId).future);
      final address = order.deliveryAddress;

      if (address.latitude != null && address.longitude != null) {
        return StopDestination(
          point: LatLng(address.latitude!, address.longitude!),
          label: address.addressLine,
          isApproximate: false,
        );
      }

      final geocoded = await ref
          .watch(geocodingServiceProvider)
          .search(address.addressLine);
      return StopDestination(
        point: geocoded,
        label: address.addressLine,
        isApproximate: geocoded != null,
      );
    });
