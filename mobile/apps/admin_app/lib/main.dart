// LPG Agency Admin Main Entry Point
import 'dart:async';

import 'package:api_client/api_client.dart';
import 'package:auth/auth.dart';
import 'package:core/core.dart';
import 'package:design_system/design_system.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:realtime/realtime.dart';

import 'src/auth_provider.dart';
import 'src/providers.dart';
import 'src/push/push_notification_service.dart';
import 'src/router.dart';
import 'src/staff_only_auth_repository.dart';

const _apiBaseUrl = String.fromEnvironment(
  'API_BASE_URL',
  defaultValue: 'https://lpg.vitessetec.com',
);

/// The `/ws` origin for [_apiBaseUrl] (same host, WebSocket scheme).
String _wsBaseUrl(String apiBaseUrl) => apiBaseUrl
    .replaceFirst('https://', 'wss://')
    .replaceFirst('http://', 'ws://');

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  final tokenStorage = SecureTokenStorage();
  late final AuthRepository authRepository;
  late final AuthController authController;
  late final RealtimeClient realtimeClient;

  final apiClient = ApiClient(
    baseUrl: _apiBaseUrl,
    getAccessToken: () => authRepository.accessToken,
    refreshAccessToken: () async {
      final result = await authRepository.restoreSession();
      return result.when(
        onSuccess: (_) {
          // Keep the live socket authorised past the old token's expiry.
          realtimeClient.updateAccessToken();
          return authRepository.accessToken;
        },
        onFailure: (_) => null,
      );
    },
    onSessionExpired: () => authController.handleSessionExpired(),
    // Requests made while the session is still being restored wait for it.
    waitForSession: () => authController.whenSettled,
  );

  authRepository = StaffOnlyAuthRepository(
    ApiAuthRepository(
      authApi: AuthApi(apiClient.dio),
      tokenStorage: tokenStorage,
    ),
  );
  authController = AuthController(authRepository);

  // Live order and notification updates over `/ws`. Connects on the first
  // subscription (the shell's, once signed in) and reconnects with backoff.
  realtimeClient = RealtimeClient(
    wsBaseUrl: _wsBaseUrl(_apiBaseUrl),
    getAccessToken: () => authRepository.accessToken,
    // The socket's token was rejected (expired): any authenticated call runs
    // the API client's single 401 -> refresh path, and the socket's own
    // reconnect then picks up the new token.
    onTokenRejected: () async {
      await NotificationApi(apiClient.dio).getUnreadCount();
    },
  );
  _wireRealtimeToAuth(authController, realtimeClient);

  // Push notifications. Isolated in try/catch: a missing/invalid
  // google-services.json (or a device without Play Services) must not take
  // the whole app down — live updates over `/ws` still work without push.
  final pushService = PushNotificationService(NotificationApi(apiClient.dio));
  try {
    await Firebase.initializeApp();
    FirebaseMessaging.onBackgroundMessage(firebaseMessagingBackgroundHandler);
    await pushService.init();
    _wirePushRegistrationToAuth(authController, pushService);
  } catch (_) {
    // Best effort: nothing to show the user for this failure.
  }

  runApp(
    ProviderScope(
      // One quiet retry of a transient failure (the skeleton stays on screen
      // meanwhile), then the error/Retry state. Riverpod's default retries ten
      // times and hides a real error; no retry at all showed an error for a
      // blip a second attempt clears (story 0.4).
      retry: quietRetry,
      overrides: [
        authControllerProvider.overrideWithValue(authController),
        apiClientProvider.overrideWithValue(apiClient),
        realtimeClientProvider.overrideWithValue(realtimeClient),
        pushNotificationServiceProvider.overrideWithValue(pushService),
      ],
      child: const AdminApp(),
    ),
  );
}

/// Register this device's FCM token whenever a session becomes active. The
/// first authenticated transition after startup covers both fresh logins and
/// restored sessions.
void _wirePushRegistrationToAuth(
  AuthController authController,
  PushNotificationService pushService,
) {
  var wasAuthenticated =
      authController.state.status == AuthStatus.authenticated;
  if (wasAuthenticated) unawaited(pushService.registerWithBackend());

  authController.addListener(() {
    final isAuthenticated =
        authController.state.status == AuthStatus.authenticated;
    if (isAuthenticated && !wasAuthenticated) {
      unawaited(pushService.registerWithBackend());
    }
    wasAuthenticated = isAuthenticated;
  });
}

/// Pauses the socket while signed out and resumes it on sign-in.
void _wireRealtimeToAuth(
  AuthController authController,
  RealtimeClient realtimeClient,
) {
  void sync() {
    if (authController.state.status == AuthStatus.authenticated) {
      realtimeClient.resume();
    } else {
      unawaited(realtimeClient.pause());
    }
  }

  sync();
  authController.addListener(sync);
}

class AdminApp extends ConsumerStatefulWidget {
  const AdminApp({super.key});

  @override
  ConsumerState<AdminApp> createState() => _AdminAppState();
}

class _AdminAppState extends ConsumerState<AdminApp> {
  StreamSubscription<String>? _tapSub;
  late final DeepLinkGate _links;
  late final AuthController _auth;

  @override
  void initState() {
    super.initState();
    final pushService = ref.read(pushNotificationServiceProvider);

    // A tapped notification may arrive before the session is restored (cold
    // start) or while signed out; the gate holds the route until sign-in so
    // the auth guard cannot swallow it.
    final auth = ref.read(authControllerProvider);
    _auth = auth;
    _links = DeepLinkGate(
      isAuthenticated: () => auth.state.isAuthenticated,
      go: (route) => ref.read(routerProvider).go(route),
    );
    auth.addListener(_flushLinks);

    final initialRoute = pushService.takeInitialRoute();
    if (initialRoute != null) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) _links.open(initialRoute);
      });
    }

    // Taps while the app is already running.
    _tapSub = pushService.taps.listen((route) {
      if (mounted) _links.open(route);
    });
  }

  void _flushLinks() {
    // After the frame, so the router's own sign-in redirect has settled.
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) _links.flush();
    });
  }

  @override
  void dispose() {
    _auth.removeListener(_flushLinks);
    _tapSub?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final router = ref.watch(routerProvider);

    return MaterialApp.router(
      title: 'LPG Agency Admin',
      theme: LpgTheme.light,
      darkTheme: LpgTheme.dark,
      highContrastTheme: LpgTheme.highContrast,
      routerConfig: router,
    );
  }
}
