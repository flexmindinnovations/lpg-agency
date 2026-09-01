import 'package:api_client/api_client.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:latlong2/latlong.dart';

import '../../../providers.dart';
import 'geocoding_service.dart';

/// Static context the tracking screen needs beyond the order itself.
class OrderTrackingView {
  const OrderTrackingView({
    required this.destination,
    required this.destinationLabel,
    required this.destinationIsApproximate,
    required this.status,
    required this.routeStatus,
    required this.lastKnownDriverLocation,
  });

  /// Delivery location. `null` when the address had no stored pin and
  /// geocoding the free-text address also failed.
  final LatLng? destination;
  final String destinationLabel;

  /// `true` when [destination] came from geocoding the address string
  /// rather than a pin — show it as "approximate".
  final bool destinationIsApproximate;

  /// The order's own status.
  final String status;

  /// The delivery route's status (`in_progress` etc.), `null` if the order
  /// isn't on a route yet.
  final String? routeStatus;

  /// Seed position for the live driver marker — the driver's last-known
  /// location at the time the screen opened. `null` until the driver starts
  /// sharing.
  final DriverLocationSnapshot? lastKnownDriverLocation;

  bool get hasLocation => destination != null;
  bool get isRouteActive => routeStatus == 'in_progress';
}

/// One-shot fetch of the order-tracking read model, with a geocode fallback
/// for the destination. `autoDispose` so the geocode cache is released when
/// the tracking screen closes.
final orderTrackingProvider = FutureProvider.autoDispose
    .family<OrderTrackingView, String>((ref, orderId) async {
      final result = await ref.watch(orderApiProvider).getOrderTracking(orderId);
      final tracking = result.when(
        onSuccess: (data) => data,
        onFailure: (failure) => throw Exception(failure.message),
      );

      LatLng? destination;
      var approximate = false;
      if (tracking.destinationLatitude != null &&
          tracking.destinationLongitude != null) {
        destination = LatLng(
          tracking.destinationLatitude!,
          tracking.destinationLongitude!,
        );
      } else {
        final geocoded = await ref
            .watch(geocodingServiceProvider)
            .search(tracking.destinationLabel);
        destination = geocoded;
        approximate = geocoded != null;
      }

      return OrderTrackingView(
        destination: destination,
        destinationLabel: tracking.destinationLabel,
        destinationIsApproximate: approximate,
        status: tracking.status,
        routeStatus: tracking.routeStatus,
        lastKnownDriverLocation: tracking.driverLocation,
      );
    });

/// The driver's current position for an order.
class DriverPosition {
  const DriverPosition({
    required this.point,
    required this.heading,
    required this.at,
  });

  final LatLng point;
  final double? heading;
  final DateTime at;
}

/// The live driver marker: seeds with the tracking read model's last-known
/// position, then follows the backend's `driver.location` messages.
/// `autoDispose` releases the underlying `/ws` subscription intent when the
/// tracking screen closes.
final driverLocationProvider = StreamProvider.autoDispose
    .family<DriverPosition?, String>((ref, orderId) async* {
      final view = await ref.watch(orderTrackingProvider(orderId).future);

      final seed = view.lastKnownDriverLocation;
      yield seed == null
          ? null
          : DriverPosition(
              point: LatLng(seed.latitude, seed.longitude),
              heading: seed.heading,
              at: seed.recordedAt,
            );

      final client = ref.watch(realtimeClientProvider);
      await for (final message in client.subscribeToDriverLocation(orderId)) {
        final lat = (message['latitude'] as num?)?.toDouble();
        final lng = (message['longitude'] as num?)?.toDouble();
        if (lat == null || lng == null) continue;
        yield DriverPosition(
          point: LatLng(lat, lng),
          heading: (message['heading'] as num?)?.toDouble(),
          at: DateTime.now(),
        );
      }
    });
