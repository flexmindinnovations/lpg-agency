import 'package:api_client/api_client.dart';
import 'package:core/core.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../api_result.dart';
import '../../../providers.dart';

/// What the order list asks the server for: a free-text [search] (order
/// number, customer name, phone or consumer number) and, when the chosen
/// filter covers a single status, that [status].
class OrderQuery {
  const OrderQuery({this.search = '', this.status});

  final String search;
  final String? status;

  @override
  bool operator ==(Object other) =>
      other is OrderQuery && other.search == search && other.status == status;

  @override
  int get hashCode => Object.hash(search, status);
}

const orderPageSize = 50;

/// One page (1-based) of the order queue, newest first.
final adminOrdersProvider =
    FutureProvider.family<OrderPageResponse, (OrderQuery, int)>((
      ref,
      args,
    ) async {
      final orderApi = ref.watch(orderApiProvider);
      final (query, page) = args;
      final result = await orderApi.getMyOrders(
        page: page,
        size: orderPageSize,
        status: query.status,
        search: query.search.trim(),
      );
      return unwrap(result);
    });

/// Cylinder types a customer can be booked for right now (active, priced for
/// them at their branch, in stock), with today's price and stock left.
final orderableCylindersProvider =
    FutureProvider.family<List<OrderableCylinderTypeResponse>, String>((
      ref,
      customerId,
    ) async {
      final result = await ref
          .watch(cylinderTypeApiProvider)
          .listOrderable(customerId: customerId);
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

/// Customers matching [search] (name, phone or consumer number); every
/// customer, first page, when empty.
final customerSearchProvider = FutureProvider.autoDispose
    .family<CustomerPageResponse, String>((ref, search) async {
      final result = await ref
          .watch(customerApiProvider)
          .listCustomers(
            skip: 0,
            limit: 30,
            search: search.isEmpty ? null : search,
          );
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

/// Scales in service, for the load-out weighment form. A role without
/// `weighment:record` gets an empty list rather than an error.
final activeScalesProvider = FutureProvider.autoDispose<List<ScaleSummary>>((
  ref,
) async {
  final result = await ref.watch(weighmentApiProvider).listActiveScales();
  return switch (result) {
    Success(:final value) => value,
    FailureResult() => const [],
  };
});

/// Load-out checks already on file for a trip.
final routeWeighmentsProvider = FutureProvider.autoDispose
    .family<List<WeighmentRecord>, String>((ref, routeId) async {
      final result = await ref
          .watch(weighmentApiProvider)
          .listForRoute(routeId);
      return unwrap(result);
    });
