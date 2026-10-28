import 'package:api_client/api_client.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:realtime/realtime.dart';

import 'push/push_notification_service.dart';

/// Provides the singleton [ApiClient] instance.
final apiClientProvider = Provider<ApiClient>((ref) {
  throw UnimplementedError('apiClientProvider was not overridden');
});

/// Provides the [AuthApi] client (`/auth/me`).
final authApiProvider = Provider<AuthApi>((ref) {
  final apiClient = ref.watch(apiClientProvider);
  return AuthApi(apiClient.dio);
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

/// Provides the [CylinderTypeApi] client.
final cylinderTypeApiProvider = Provider<CylinderTypeApi>((ref) {
  final apiClient = ref.watch(apiClientProvider);
  return CylinderTypeApi(apiClient.dio);
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

/// Provides the [FleetApi] client (drivers, vans, godowns, stock).
final fleetApiProvider = Provider<FleetApi>((ref) {
  final apiClient = ref.watch(apiClientProvider);
  return FleetApi(apiClient.dio);
});

/// Provides the [WeighmentApi] client (scales, load-out checks).
final weighmentApiProvider = Provider<WeighmentApi>((ref) {
  final apiClient = ref.watch(apiClientProvider);
  return WeighmentApi(apiClient.dio);
});

/// Provides the [NotificationApi] client.
final notificationApiProvider = Provider<NotificationApi>((ref) {
  final apiClient = ref.watch(apiClientProvider);
  return NotificationApi(apiClient.dio);
});

/// The shared `/ws` connection. `main()` overrides this.
final realtimeClientProvider = Provider<RealtimeClient>((ref) {
  throw UnimplementedError('realtimeClientProvider was not overridden');
});

/// Owns FCM for the Admin App. `main()` overrides this.
final pushNotificationServiceProvider = Provider<PushNotificationService>((
  ref,
) {
  throw UnimplementedError(
    'pushNotificationServiceProvider was not overridden',
  );
});
