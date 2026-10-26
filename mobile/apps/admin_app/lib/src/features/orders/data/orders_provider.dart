import 'package:api_client/api_client.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../api_result.dart';
import '../../../providers.dart';

final adminOrdersProvider = FutureProvider.family<OrderPageResponse, int>((ref, page) async {
  final orderApi = ref.watch(orderApiProvider);
  final result = await orderApi.getMyOrders(page: page, size: 50);
  return unwrap(result);
});

final adminOrderDetailProvider = FutureProvider.family<OrderResponse, String>((ref, orderId) async {
  final orderApi = ref.watch(orderApiProvider);
  final result = await orderApi.getOrder(orderId);
  return unwrap(result);
});

final availableRoutesProvider = FutureProvider<List<RouteSummary>>((ref) async {
  final routeApi = ref.watch(routeApiProvider);
  final result = await routeApi.listRoutes();
  return unwrap(result);
});

final availableCustomersProvider = FutureProvider<CustomerPageResponse>((ref) async {
  final customerApi = ref.watch(customerApiProvider);
  final result = await customerApi.listCustomers(skip: 0, limit: 100);
  return unwrap(result);
});

final cylinderCatalogProvider = FutureProvider<List<CylinderTypeResponse>>((ref) async {
  final cylinderTypeApi = ref.watch(cylinderTypeApiProvider);
  final result = await cylinderTypeApi.list();
  return unwrap(result);
});
