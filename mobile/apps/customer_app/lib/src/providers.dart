import 'package:api_client/api_client.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:local_storage/local_storage.dart';
import 'package:sync_engine/sync_engine.dart';

/// Provides the singleton [DriftLocalDatabase] instance.
/// Must be overridden in `main.dart` with the initialized instance.
final localDatabaseProvider = Provider<DriftLocalDatabase>((ref) {
  throw UnimplementedError('localDatabaseProvider was not overridden');
});

/// Provides the singleton [SyncCoordinator] instance.
/// Must be overridden in `main.dart` with the initialized instance.
final syncCoordinatorProvider = Provider<SyncCoordinator>((ref) {
  throw UnimplementedError('syncCoordinatorProvider was not overridden');
});

/// Provides the singleton [ApiClient] instance.
/// Must be overridden in `main.dart` with the initialized instance.
final apiClientProvider = Provider<ApiClient>((ref) {
  throw UnimplementedError('apiClientProvider was not overridden');
});

/// Provides the [CustomerApi] client.
final customerApiProvider = Provider<CustomerApi>((ref) {
  final apiClient = ref.watch(apiClientProvider);
  return CustomerApi(apiClient.dio);
});

/// Provides the [OrderApi] client.
final orderApiProvider = Provider<OrderApi>((ref) {
  final apiClient = ref.watch(apiClientProvider);
  return OrderApi(apiClient.dio);
});
