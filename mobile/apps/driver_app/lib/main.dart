import 'dart:async';

import 'package:api_client/api_client.dart';
import 'package:auth/auth.dart';
import 'package:design_system/design_system.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:local_storage/local_storage.dart';
import 'package:sync_engine/sync_engine.dart';

import 'src/api_provider.dart';
import 'src/auth_provider.dart';
import 'src/local_database_provider.dart';
import 'src/push/push_notification_service.dart';
import 'src/router.dart';

/// Backend origin — no `/api/v1` suffix, `AuthApi`'s own paths already carry
/// the full `/api/v1/auth/...` prefix. Override for a real device or an
/// Android emulator (which cannot resolve `localhost` as the host machine)
/// with `--dart-define=API_BASE_URL=http://10.0.2.2:8000`.
const _apiBaseUrl = String.fromEnvironment(
  'API_BASE_URL',
  defaultValue: 'http://localhost:8000',
);

/// Driver App entry point.
///
/// Covers the active route (Today), the stop list + delivery history
/// (Deliveries), the driver's profile + logout (Profile), the per-stop
/// workflow (depart → record delivery / proof-of-delivery → payment),
/// background live-location sharing, and FCM push (new-delivery alerts).
/// Offline-first sync of the delivery workflow is still a future phase.
///
/// The on-device database and the auth session are both established here,
/// before the first frame, so the rest of the app can assume both are
/// always ready (ADR-008 offline-first; Phase 6 authentication).
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

  // Push notifications. Isolated in try/catch: a missing/invalid
  // google-services.json (or a device without Play Services) must not take
  // the whole app down — everything else works fine without push.
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
        authControllerProvider.overrideWithValue(authController),
        apiClientProvider.overrideWithValue(apiClient),
        pushNotificationServiceProvider.overrideWithValue(pushService),
      ],
      child: const DriverApp(),
    ),
  );
}

/// Register this device's FCM token whenever a session becomes active, and
/// forget it on logout. The first authenticated transition after startup
/// covers both fresh logins and restored sessions.
void _wirePushRegistrationToAuth(
  AuthController authController,
  PushNotificationService pushService,
) {
  var wasAuthenticated = authController.state.status == AuthStatus.authenticated;
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

class DriverApp extends ConsumerStatefulWidget {
  const DriverApp({super.key});

  @override
  ConsumerState<DriverApp> createState() => _DriverAppState();
}

class _DriverAppState extends ConsumerState<DriverApp> {
  StreamSubscription<String>? _tapSub;

  @override
  void initState() {
    super.initState();
    final pushService = ref.read(pushNotificationServiceProvider);

    // A notification that cold-started the app: navigate once the router is
    // ready.
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
