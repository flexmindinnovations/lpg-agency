import 'dart:async';
import 'dart:convert';
import 'dart:io' show Platform;

import 'package:api_client/api_client.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';

/// Must match the `default_notification_channel_id` meta-data in
/// AndroidManifest.xml — the OS uses that channel for background/killed
/// messages, and we create the same one here for the foreground path so a
/// notification looks identical either way.
const _androidChannelId = 'lpg_default_channel';
const _androidChannelName = 'Order & account updates';

/// Owns the FCM lifecycle for the customer app: permission, token
/// registration with the backend, and turning received messages into either
/// a visible notification (foreground) or a navigation (tap).
///
/// Deliberately free of Firebase *initialization* — `Firebase.initializeApp`
/// runs in `main()` before this is constructed, and the top-level
/// [firebaseMessagingBackgroundHandler] is registered there too (it has to
/// be a top-level function for the background isolate).
class PushNotificationService {
  PushNotificationService(this._notificationApi);

  final NotificationApi _notificationApi;
  final _localNotifications = FlutterLocalNotificationsPlugin();
  final _tapController = StreamController<String>.broadcast();

  StreamSubscription<RemoteMessage>? _onMessageSub;
  StreamSubscription<RemoteMessage>? _onOpenedSub;
  StreamSubscription<String>? _onTokenRefreshSub;
  String? _initialRoute;
  bool _initialised = false;

  /// Route strings emitted when the user taps a notification while the app
  /// is running. `CustomerApp` listens and calls `router.go`.
  Stream<String> get taps => _tapController.stream;

  /// A route derived from the notification that cold-started the app, if
  /// any. Read once, early, by `CustomerApp`.
  String? takeInitialRoute() {
    final route = _initialRoute;
    _initialRoute = null;
    return route;
  }

  String get _platform {
    if (kIsWeb) return 'web';
    if (Platform.isAndroid) return 'android';
    if (Platform.isIOS) return 'ios';
    return 'web';
  }

  /// Wire up handlers and ask for permission. Safe to call more than once.
  Future<void> init() async {
    if (_initialised) return;
    _initialised = true;

    await FirebaseMessaging.instance.requestPermission();

    await _localNotifications.initialize(
      const InitializationSettings(
        android: AndroidInitializationSettings('@mipmap/ic_launcher'),
        iOS: DarwinInitializationSettings(),
      ),
      onDidReceiveNotificationResponse: (response) {
        final payload = response.payload;
        if (payload != null && payload.isNotEmpty) {
          _emitTapFromData(_decodePayload(payload));
        }
      },
    );

    await _localNotifications
        .resolvePlatformSpecificImplementation<
          AndroidFlutterLocalNotificationsPlugin
        >()
        ?.createNotificationChannel(
          const AndroidNotificationChannel(
            _androidChannelId,
            _androidChannelName,
            importance: Importance.high,
          ),
        );

    _onMessageSub = FirebaseMessaging.onMessage.listen(_showForeground);
    _onOpenedSub = FirebaseMessaging.onMessageOpenedApp.listen(
      (m) => _emitTapFromData(m.data),
    );
    _onTokenRefreshSub = FirebaseMessaging.instance.onTokenRefresh.listen(
      _sendToken,
    );

    final initial = await FirebaseMessaging.instance.getInitialMessage();
    if (initial != null) {
      _initialRoute = _routeFromData(initial.data);
    }
  }

  /// Register the current device token with the backend. Call once the user
  /// is authenticated (the endpoint needs a bearer token).
  Future<void> registerWithBackend() async {
    final token = await FirebaseMessaging.instance.getToken();
    if (token != null) await _sendToken(token);
  }

  /// Drop this device's token — call just before logout so a shared device
  /// stops getting the previous user's notifications.
  Future<void> unregister() async {
    final token = await FirebaseMessaging.instance.getToken();
    if (token == null) return;
    await _notificationApi.unregisterDevice(token);
  }

  Future<void> _sendToken(String token) async {
    final result = await _notificationApi.registerDevice(
      token: token,
      platform: _platform,
    );
    result.when(
      onSuccess: (_) {},
      onFailure: (f) =>
          debugPrint('push: device registration failed: ${f.message}'),
    );
  }

  Future<void> _showForeground(RemoteMessage message) async {
    final notification = message.notification;
    if (notification == null) return;
    await _localNotifications.show(
      notification.hashCode,
      notification.title,
      notification.body,
      const NotificationDetails(
        android: AndroidNotificationDetails(
          _androidChannelId,
          _androidChannelName,
          importance: Importance.high,
          priority: Priority.high,
        ),
        iOS: DarwinNotificationDetails(),
      ),
      payload: jsonEncode(message.data),
    );
  }

  void _emitTapFromData(Map<String, dynamic> data) {
    final route = _routeFromData(data);
    if (route != null) _tapController.add(route);
  }

  Map<String, dynamic> _decodePayload(String payload) {
    try {
      final decoded = jsonDecode(payload);
      return decoded is Map<String, dynamic> ? decoded : const {};
    } on FormatException {
      return const {};
    }
  }

  /// Maps the FCM `data` block (set by the backend's push channel:
  /// `type`, `reference_type`, `reference_id`) to an in-app route. Falls
  /// back to the notifications inbox when there's nothing specific to open.
  String? _routeFromData(Map<String, dynamic> data) {
    final referenceType = data['reference_type'] as String?;
    final referenceId = data['reference_id'] as String?;
    if (referenceType == 'order' && referenceId != null) {
      return '/orders/$referenceId';
    }
    if (referenceType == 'invoice' && referenceId != null) {
      return '/orders/invoices/$referenceId';
    }
    if (data.isNotEmpty) return '/notifications';
    return null;
  }

  Future<void> dispose() async {
    await _onMessageSub?.cancel();
    await _onOpenedSub?.cancel();
    await _onTokenRefreshSub?.cancel();
    await _tapController.close();
  }
}

/// Background/terminated-state message handler. FCM shows the tray
/// notification itself for messages that carry a `notification` block, so
/// there's nothing to render here — this exists because the plugin requires
/// a registered top-level handler, and it's where any data-only background
/// work (badge counts, cache priming) would go later.
@pragma('vm:entry-point')
Future<void> firebaseMessagingBackgroundHandler(RemoteMessage message) async {
  // No Firebase.initializeApp() here: flutter_firebase's background isolate
  // initialises the default app from the native config automatically.
}
