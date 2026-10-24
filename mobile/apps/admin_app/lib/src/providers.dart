import 'package:api_client/api_client.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

/// Provides the singleton [ApiClient] instance.
final apiClientProvider = Provider<ApiClient>((ref) {
  throw UnimplementedError('apiClientProvider was not overridden');
});

/// Provides the [AdminApi] client for admin operations.
final adminApiProvider = Provider<AdminApi>((ref) {
  final apiClient = ref.watch(apiClientProvider);
  return AdminApi(apiClient.dio);
});

/// Provides the [OrderApi] client.
final orderApiProvider = Provider<OrderApi>((ref) {
  final apiClient = ref.watch(apiClientProvider);
  return OrderApi(apiClient.dio);
});

/// Provides the [CustomerApi] client.
final customerApiProvider = Provider<CustomerApi>((ref) {
  final apiClient = ref.watch(apiClientProvider);
  return CustomerApi(apiClient.dio);
});

/// Provides the [RouteApi] client.
final routeApiProvider = Provider<RouteApi>((ref) {
  final apiClient = ref.watch(apiClientProvider);
  return RouteApi(apiClient.dio);
});

/// Provides the [KycApi] client.
final kycApiProvider = Provider<KycApi>((ref) {
  final apiClient = ref.watch(apiClientProvider);
  return KycApi(apiClient.dio);
});

/// Provides the [CashHandoverApi] client.
final cashHandoverApiProvider = Provider<CashHandoverApi>((ref) {
  final apiClient = ref.watch(apiClientProvider);
  return CashHandoverApi(apiClient.dio);
});

/// Provides the [ComplaintApi] client.
final complaintApiProvider = Provider<ComplaintApi>((ref) {
  final apiClient = ref.watch(apiClientProvider);
  return ComplaintApi(apiClient.dio);
});
