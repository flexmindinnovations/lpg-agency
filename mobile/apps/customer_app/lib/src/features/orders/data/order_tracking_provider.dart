import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:latlong2/latlong.dart';

import 'geocoding_service.dart';
import 'orders_provider.dart';

/// Everything the tracking screen's map needs for one order.
class OrderTrackingView {
  const OrderTrackingView({
    required this.destination,
    required this.destinationLabel,
    required this.destinationIsApproximate,
    required this.status,
  });

  /// Delivery location. `null` when the address had no stored pin and
  /// geocoding the free-text address also failed.
  final LatLng? destination;
  final String destinationLabel;

  /// `true` when [destination] came from geocoding the address string rather
  /// than a pin the customer set — show it as "approximate".
  final bool destinationIsApproximate;

  final String status;

  bool get hasLocation => destination != null;
}

/// Resolves the delivery destination for an order's tracking map: the address
/// pin if one was saved, otherwise a best-effort geocode of the address text.
///
/// `autoDispose` so the geocode cache and any downstream live subscription are
/// released when the tracking screen closes.
final orderTrackingProvider = FutureProvider.autoDispose
    .family<OrderTrackingView, String>((ref, orderId) async {
      final order = await ref.watch(orderDetailProvider(orderId).future);
      final address = order.deliveryAddress;

      if (address.latitude != null && address.longitude != null) {
        return OrderTrackingView(
          destination: LatLng(address.latitude!, address.longitude!),
          destinationLabel: address.addressLine,
          destinationIsApproximate: false,
          status: order.status,
        );
      }

      final geocoded = await ref
          .watch(geocodingServiceProvider)
          .search(address.addressLine);

      return OrderTrackingView(
        destination: geocoded,
        destinationLabel: address.addressLine,
        destinationIsApproximate: geocoded != null,
        status: order.status,
      );
    });
