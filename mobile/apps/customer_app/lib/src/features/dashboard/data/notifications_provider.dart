import 'package:api_client/api_client.dart';
import 'package:auth/auth.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

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

/// Live `notification.new` events for the signed-in user, over the
/// backend's `/ws` (`RealtimeClient.subscribeToNotifications`). The message
/// carries the notification's id, title, body and `reference_type`/
/// `reference_id` (`realtime_handlers.py`'s `on_notification_created`);
/// callers still refetch [notificationsProvider]/
/// [unreadNotificationCountProvider] for the list itself.
final notificationsRealtimeProvider =
    StreamProvider.autoDispose<Map<String, dynamic>>((ref) {
      final client = ref.watch(realtimeClientProvider);
      return client.subscribeToNotifications();
    });
