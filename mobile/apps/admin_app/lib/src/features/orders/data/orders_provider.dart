import 'package:api_client/api_client.dart';
import 'package:core/core.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../providers.dart';

final adminOrdersProvider = FutureProvider.family<OrderPageResponse, int>((ref, page) async {
  final orderApi = ref.watch(orderApiProvider);
  final result = await orderApi.getMyOrders(page: page, size: 50);
  return switch (result) {
    Success(:final value) => value,
    FailureResult(:final failure) => throw Exception(failure.message),
  };
});

final adminOrderDetailProvider = FutureProvider.family<OrderResponse, String>((ref, orderId) async {
  final orderApi = ref.watch(orderApiProvider);
  final result = await orderApi.getOrder(orderId);
  return switch (result) {
    Success(:final value) => value,
    FailureResult(:final failure) => throw Exception(failure.message),
  };
});

final availableRoutesProvider = FutureProvider<List<RouteSummary>>((ref) async {
  final routeApi = ref.watch(routeApiProvider);
  final result = await routeApi.listRoutes();
  return switch (result) {
    Success(:final value) => value,
    FailureResult(:final failure) => throw Exception(failure.message),
  };
});
