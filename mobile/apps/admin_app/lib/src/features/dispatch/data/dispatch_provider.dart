import 'package:api_client/api_client.dart';
import 'package:core/core.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../api_result.dart';
import '../../../providers.dart';
import '../domain/trip_status.dart';

/// Open and in-progress trips across every branch, busiest first.
final dispatchTripsProvider = FutureProvider<List<RouteSummary>>((ref) async {
  final api = ref.watch(routeApiProvider);
  final pages = await Future.wait([
    for (final status in activeTripStatuses)
      api.listRoutes(status: status, pageSize: 100),
  ]);
  final trips = <RouteSummary>[];
  for (final page in pages) {
    switch (page) {
      case Success<List<RouteSummary>>(:final value):
        trips.addAll(value);
      case FailureResult<List<RouteSummary>>(:final failure):
        throw ApiException(failure);
    }
  }
  trips.sort((a, b) => compareTrips(a.status, b.status));
  return trips;
});

/// Confirmed orders that are not on a trip yet.
final ordersWaitingForTripProvider = FutureProvider<List<OrderResponse>>((
  ref,
) async {
  final result = await ref
      .watch(orderApiProvider)
      .getMyOrders(status: 'confirmed', size: 100);
  return unwrap(result).items;
});
