import 'package:api_client/api_client.dart';
import 'package:auth/auth.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../api_provider.dart';
import '../../../auth_provider.dart';

/// The driver's notification history — the Alerts tab. `autoDispose`: only
/// that screen reads it.
final driverNotificationsProvider =
    FutureProvider.autoDispose<List<NotificationResponse>>((ref) async {
      final auth = ref.watch(authControllerProvider);
      if (auth.state.status != AuthStatus.authenticated) return const [];
      final result = await ref
          .watch(notificationApiProvider)
          .getMyNotifications();
      return result.when(
        onSuccess: (page) => page.items,
        onFailure: (failure) => throw Exception(failure.message),
      );
    });

/// Unread count for the shell's Alerts-tab badge. Not `autoDispose` — the
/// shell watches it for the whole session. A failure reads as 0 (no badge)
/// rather than an error.
final unreadNotificationCountProvider = FutureProvider<int>((ref) async {
  final auth = ref.watch(authControllerProvider);
  if (auth.state.status != AuthStatus.authenticated) return 0;
  final result = await ref.watch(notificationApiProvider).getUnreadCount();
  return result.when(onSuccess: (count) => count, onFailure: (_) => 0);
});

/// Ticks when an FCM message lands while the app is foregrounded — the shell
/// listens and invalidates the count/list/route.
final pushMessagesProvider = StreamProvider<void>((ref) {
  return ref.watch(pushNotificationServiceProvider).messages;
});

/// Live updates for the signed-in driver over `/ws`
/// (`RealtimeClient.subscribeToDriverUpdates`): new notifications (a new
/// stop, a cancelled stop, the route being ready), reads made on another
/// device, route changes on the driver's own channel, and a reconnect marker
/// after a dropped connection. Covers the case push can't: a device where
/// FCM isn't available or the push was dropped.
final notificationsRealtimeProvider =
    StreamProvider.autoDispose<Map<String, dynamic>>((ref) {
      return ref.watch(realtimeClientProvider).subscribeToDriverUpdates();
    });
