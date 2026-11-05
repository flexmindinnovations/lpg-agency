import 'dart:async';

import 'package:api_client/api_client.dart';
import 'package:auth/auth.dart';
import 'package:core/core.dart';
import 'package:design_system/design_system.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:local_storage/local_storage.dart';
import 'package:realtime/realtime.dart';
import 'package:sync_engine/sync_engine.dart';

import 'src/auth_provider.dart';
import 'src/i18n/customer_strings.dart';
import 'src/features/orders/data/orders_provider.dart';
import 'src/providers.dart';
import 'src/push/push_notification_service.dart';
import 'src/router.dart';

/// Backend origin - no `/api/v1` suffix, `AuthApi`'s own paths already carry
/// the full `/api/v1/auth/...` prefix. Defaults to the production server; for
/// local development override it, e.g. for the Android emulator (which cannot
/// resolve `localhost` as the host machine)
/// `--dart-define=API_BASE_URL=http://10.0.2.2:8000`.
const _apiBaseUrl = String.fromEnvironment(
  'API_BASE_URL',
  defaultValue: 'https://lpg.vitessetec.com',
);

/// `RealtimeClient` wants a `ws(s)://` origin, not `http(s)://` --
/// `_apiBaseUrl` stays the single source of truth (one `--dart-define` for
/// both) rather than adding a second override to keep in sync.
String _wsBaseUrl(String apiBaseUrl) => apiBaseUrl
    .replaceFirst('https://', 'wss://')
    .replaceFirst('http://', 'ws://');

/// Customer App entry point.
///
/// Shell only beyond authentication. Registration, booking, tracking,
/// payments and complaints are each built in their own phase, behind their
/// own plan.
///
/// `WidgetsFlutterBinding.ensureInitialized()` is required here now (unlike
/// the original Phase 5 shell) - `SecureTokenStorage`'s startup session
/// restore touches a platform channel shortly after `runApp` returns.
void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  final localDatabase = DriftLocalDatabase();
  await localDatabase.open();

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
  );
  authRepository = ApiAuthRepository(
    authApi: AuthApi(apiClient.dio),
    tokenStorage: tokenStorage,
  );
  authController = AuthController(authRepository);

  final syncCoordinator = SyncCoordinator(
    database: localDatabase.database,
    apiClient: apiClient,
  );
  syncCoordinator.start();

  realtimeClient = RealtimeClient(
    wsBaseUrl: _wsBaseUrl(_apiBaseUrl),
    getAccessToken: () => authRepository.accessToken,
    // The socket's token was rejected (expired): any authenticated call
    // runs the API client's single 401 -> refresh path, and the socket's
    // own reconnect then picks up the new token.
    onTokenRejected: () async {
      await NotificationApi(apiClient.dio).getUnreadCount();
    },
  );
  _wireRealtimeToAuth(authController, realtimeClient);

  // Push notifications. Isolated in try/catch: a missing/invalid
  // google-services.json (or GoogleService-Info.plist) must not take the
  // whole app down — the rest of it works fine without push.
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
      overrides: [
        localDatabaseProvider.overrideWithValue(localDatabase),
        syncCoordinatorProvider.overrideWithValue(syncCoordinator),
        authControllerProvider.overrideWithValue(authController),
        apiClientProvider.overrideWithValue(apiClient),
        realtimeClientProvider.overrideWithValue(realtimeClient),
        pushNotificationServiceProvider.overrideWithValue(pushService),
      ],
      child: const CustomerApp(),
    ),
  );
}

/// Register this device's FCM token whenever a session becomes active, and
/// forget it on logout. `AuthController` is a `ChangeNotifier`; the first
/// authenticated transition after startup covers both fresh logins and
/// restored sessions.
void _wirePushRegistrationToAuth(
  AuthController authController,
  PushNotificationService pushService,
) {
  var wasAuthenticated = authController.state.isAuthenticated;
  if (wasAuthenticated) unawaited(pushService.registerWithBackend());

  authController.addListener(() {
    final isAuthenticated = authController.state.isAuthenticated;
    if (isAuthenticated && !wasAuthenticated) {
      unawaited(pushService.registerWithBackend());
    }
    wasAuthenticated = isAuthenticated;
  });
}

class CustomerApp extends ConsumerStatefulWidget {
  const CustomerApp({super.key});

  @override
  ConsumerState<CustomerApp> createState() => _CustomerAppState();
}

class _CustomerAppState extends ConsumerState<CustomerApp>
    with WidgetsBindingObserver {
  StreamSubscription<String>? _tapSub;
  StreamSubscription<void>? _messageSub;

  /// Refetches what a screen may have missed while the app was backgrounded
  /// or the socket was down, so a delivered order stops offering Pay and
  /// Cancel as soon as the customer looks at it again.
  void _refreshOrders() {
    ref.invalidate(ordersProvider);
    ref.invalidate(orderDetailProvider);
    ref.invalidate(pendingCancellationProvider);
    ref.invalidate(deliveryCodeProvider);
    ref.invalidate(orderHistoryProvider);
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) _refreshOrders();
  }

  late final DeepLinkGate _links;
  late final AuthController _auth;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    final pushService = ref.read(pushNotificationServiceProvider);
    _messageSub = pushService.messages.listen((_) => _refreshOrders());

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
    WidgetsBinding.instance.removeObserver(this);
    _auth.removeListener(_flushLinks);
    _tapSub?.cancel();
    _messageSub?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp.router(
      onGenerateTitle: (context) => context.strings.app.title,
      locale: ref.watch(lpgLocaleProvider),
      supportedLocales: customerLaunchLocales,
      localizationsDelegates: customerLocalizationsDelegates,
      theme: LpgTheme.light,
      darkTheme: LpgTheme.dark,
      highContrastTheme: LpgTheme.highContrast,
      highContrastDarkTheme: LpgTheme.highContrast,
      themeMode: ThemeMode.system,
      routerConfig: ref.watch(routerProvider),
      debugShowCheckedModeBanner: false,
    );
  }
}

/// Hold the live socket closed while signed out and reopen it on sign-in,
/// so it never retries with a missing token or outlives the session.
void _wireRealtimeToAuth(
  AuthController authController,
  RealtimeClient realtimeClient,
) {
  void sync() {
    if (authController.state.isAuthenticated) {
      realtimeClient.resume();
    } else {
      unawaited(realtimeClient.pause());
    }
  }

  sync();
  authController.addListener(sync);
}
