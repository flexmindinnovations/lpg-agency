import 'package:api_client/api_client.dart';
import 'package:core/core.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../api_result.dart';
import '../../../providers.dart';

final adminOrdersProvider = FutureProvider.family<OrderPageResponse, int>((
  ref,
  page,
) async {
  final orderApi = ref.watch(orderApiProvider);
  final result = await orderApi.getMyOrders(page: page, size: 50);
  return unwrap(result);
});

final adminOrderDetailProvider = FutureProvider.family<OrderResponse, String>((
  ref,
  orderId,
) async {
  final orderApi = ref.watch(orderApiProvider);
  final result = await orderApi.getOrder(orderId);
  return unwrap(result);
});

final availableRoutesProvider = FutureProvider<List<RouteSummary>>((ref) async {
  final routeApi = ref.watch(routeApiProvider);
  final result = await routeApi.listRoutes();
  return unwrap(result);
});

final availableCustomersProvider = FutureProvider<CustomerPageResponse>((
  ref,
) async {
  final customerApi = ref.watch(customerApiProvider);
  final result = await customerApi.listCustomers(skip: 0, limit: 100);
  return unwrap(result);
});

final cylinderCatalogProvider = FutureProvider<List<CylinderTypeResponse>>((
  ref,
) async {
  final cylinderTypeApi = ref.watch(cylinderTypeApiProvider);
  final result = await cylinderTypeApi.list();
  return unwrap(result);
});

/// Cylinder type names by id, so lines read "Domestic 14.2 kg", not an id.
final cylinderNamesProvider = FutureProvider<Map<String, String>>((ref) async {
  final catalog = await ref.watch(cylinderCatalogProvider.future);
  return {for (final type in catalog) type.id: type.name};
});

/// The cancellation request waiting on an order, or `null`.
final pendingCancellationProvider =
    FutureProvider.family<PendingCancellationResponse?, String>((
      ref,
      orderId,
    ) async {
      final result = await ref
          .watch(orderApiProvider)
          .getPendingCancellation(orderId);
      return unwrap(result);
    });

/// The order's status history, oldest first (the failed-delivery reason
/// lives on its last entry).
final orderHistoryProvider =
    FutureProvider.family<List<OrderStatusHistoryEntry>, String>((
      ref,
      orderId,
    ) async {
      final result = await ref
          .watch(orderApiProvider)
          .getStatusHistory(orderId);
      return unwrap(result);
    });

/// Drivers, vans and godowns the Send out sheet offers.
class FleetData {
  const FleetData({
    required this.drivers,
    required this.vehicles,
    required this.warehouses,
  });

  final List<FleetDriver> drivers;
  final List<FleetVehicle> vehicles;
  final List<FleetWarehouse> warehouses;

  String driverName(String id) {
    for (final d in drivers) {
      if (d.id == id) return d.name;
    }
    return 'the driver';
  }

  String vehicleName(String id) {
    for (final v in vehicles) {
      if (v.id == id) return v.registrationNumber;
    }
    return 'the van';
  }
}

final fleetProvider = FutureProvider<FleetData>((ref) async {
  final api = ref.watch(fleetApiProvider);
  final results = await (
    api.listDrivers(),
    api.listVehicles(),
    api.listWarehouses(),
  ).wait;
  return FleetData(
    drivers: unwrap(results.$1),
    vehicles: unwrap(results.$2),
    warehouses: unwrap(results.$3),
  );
});

/// Trips that haven't come back yet; a driver or van on one is busy.
const _activeTripStatuses = ['planned', 'loaded', 'in_progress'];

/// Open and in-progress trips of a branch. Roles without `routes:read` get
/// an empty list rather than an error.
final activeTripsProvider = FutureProvider.family<List<RouteSummary>, String>((
  ref,
  branchId,
) async {
  final api = ref.watch(routeApiProvider);
  final pages = await Future.wait([
    for (final status in _activeTripStatuses)
      api.listRoutes(status: status, branchId: branchId, pageSize: 100),
  ]);
  return [
    for (final page in pages)
      if (page is Success<List<RouteSummary>>) ...page.value,
  ];
});

/// Filled stock (cylinder type id -> count) at a `warehouse` or `vehicle`.
/// Only a guide: the server still refuses a short load.
final filledStockProvider =
    FutureProvider.family<Map<String, int>?, (String, String)>((
      ref,
      location,
    ) async {
      final result = await ref
          .watch(fleetApiProvider)
          .getFilledStock(location.$1, location.$2);
      return switch (result) {
        Success(:final value) => value,
        FailureResult() => null,
      };
    });
