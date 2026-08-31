import 'dart:async';

import 'package:api_client/api_client.dart';
import 'package:auth/auth.dart';
import 'package:design_system/design_system.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:local_storage/local_storage.dart';
import 'package:realtime/realtime.dart';
import 'package:sync_engine/sync_engine.dart';

import 'src/auth_provider.dart';
import 'src/providers.dart';
import 'src/push/push_notification_service.dart';
import 'src/router.dart';

/// Backend origin - no `/api/v1` suffix, `AuthApi`'s own paths already carry
/// the full `/api/v1/auth/...` prefix. Override for a real device or an
/// Android emulator (which cannot resolve `localhost` as the host machine)
/// with `--dart-define=API_BASE_URL=http://10.0.2.2:8000`.
const _apiBaseUrl = String.fromEnvironment(
  'API_BASE_URL',
  defaultValue: 'http://localhost:8000',
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

  final apiClient = ApiClient(
    baseUrl: _apiBaseUrl,
    getAccessToken: () => authRepository.accessToken,
    refreshAccessToken: () async {
      final result = await authRepository.restoreSession();
      return result.when(
        onSuccess: (_) => authRepository.accessToken,
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

  final realtimeClient = RealtimeClient(
    wsBaseUrl: _wsBaseUrl(_apiBaseUrl),
    getAccessToken: () => authRepository.accessToken,
  );

  // Push notifications. Isolated in try/catch: a missing/invalid
  // google-services.json (or GoogleService-Info.plist) must not take the
  // whole app down — the rest of it works fine without push.
  final pushService = PushNotificationService(NotificationApi(apiClient.dio));
  try {
    await Firebase.initializeApp();
    FirebaseMessaging.onBackgroundMessage(firebaseMessagingBackgroundHandler);
    await pushService.init();
    _wirePushRegistrationToAuth(authController, pushService);
  } catch (e, s) {
    debugPrint('push: initialisation skipped ($e)\n$s');
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

class _CustomerAppState extends ConsumerState<CustomerApp> {
  StreamSubscription<String>? _tapSub;

  @override
  void initState() {
    super.initState();
    final pushService = ref.read(pushNotificationServiceProvider);

    // A notification that cold-started the app: navigate once the first
    // frame (and the router) is ready.
    final initialRoute = pushService.takeInitialRoute();
    if (initialRoute != null) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) ref.read(routerProvider).go(initialRoute);
      });
    }

    // Taps while the app is already running.
    _tapSub = pushService.taps.listen((route) {
      if (mounted) ref.read(routerProvider).go(route);
    });
  }

  @override
  void dispose() {
    _tapSub?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp.router(
      title: 'LPG Agency',
      theme: LpgTheme.light,
      darkTheme: LpgTheme.dark,
      themeMode: ThemeMode.system,
      routerConfig: ref.watch(routerProvider),
      debugShowCheckedModeBanner: false,
    );
  }
}
