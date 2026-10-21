import 'package:api_client/api_client.dart';
import 'package:auth/auth.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:realtime/realtime.dart';

import '../../../auth_provider.dart';
import '../../../providers.dart';

/// Provides the current customer's notifications.
final notificationsProvider = FutureProvider<List<NotificationResponse>>((
  ref,
) async {
  final api = ref.watch(notificationApiProvider);
  final authController = ref.watch(authControllerProvider);

  if (authController.state.status == AuthStatus.authenticated &&
      authController.state.principal != null) {
    final result = await api.getMyNotifications();
    return result.when(
      onSuccess: (data) => data.items,
      onFailure: (failure) => throw Exception(failure.message),
    );
  }

  return [];
});

/// Provides the unread notification count.
final unreadNotificationCountProvider = FutureProvider<int>((ref) async {
  final api = ref.watch(notificationApiProvider);
  final authController = ref.watch(authControllerProvider);

  if (authController.state.status == AuthStatus.authenticated &&
      authController.state.principal != null) {
    final result = await api.getUnreadCount();
    return result.when(onSuccess: (count) => count, onFailure: (failure) => 0);
  }

  return 0;
});

/// Live inbox changes for the signed-in user over the backend's `/ws`
/// (`RealtimeClient.subscribeToNotificationChanges`): `notification.new`
/// (carrying id, title, body and `reference_type`/`reference_id`), reads
/// made on another device (`notification.read`/`notification.read_all`),
/// and a synthetic [reconnectedMessageType] after a dropped connection.
/// Listeners refetch [notificationsProvider]/[unreadNotificationCountProvider]
/// on every event.
final notificationsRealtimeProvider =
    StreamProvider.autoDispose<Map<String, dynamic>>((ref) {
      final client = ref.watch(realtimeClientProvider);
      return client.subscribeToNotificationChanges();
    });
