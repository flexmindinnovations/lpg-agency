import 'package:api_client/api_client.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../api_result.dart';
import '../../../providers.dart';

/// The signed-in user's notification history, newest first — the Alerts tab.
final adminNotificationsProvider =
    FutureProvider.autoDispose<List<NotificationResponse>>((ref) async {
      final result = await ref
          .watch(notificationApiProvider)
          .getMyNotifications();
      return unwrap(result).items;
    });

/// Unread count for the Alerts tab badge. A failure reads as 0 (no badge)
/// rather than an error.
final unreadNotificationCountProvider = FutureProvider<int>((ref) async {
  final result = await ref.watch(notificationApiProvider).getUnreadCount();
  return result.when(onSuccess: (count) => count, onFailure: (_) => 0);
});

/// Live updates for an office user over `/ws`: every order status change in
/// the tenant, new notifications, reads made on another device, and a
/// reconnect marker after a dropped connection. The app shell listens for
/// the whole session.
final staffRealtimeProvider = StreamProvider<Map<String, dynamic>>((ref) {
  return ref.watch(realtimeClientProvider).subscribeToStaffUpdates();
});

/// Ticks when an FCM message lands while the app is foregrounded — the shell
/// listens and refreshes the badge and inbox.
final pushMessagesProvider = StreamProvider<void>((ref) {
  return ref.watch(pushNotificationServiceProvider).messages;
});
