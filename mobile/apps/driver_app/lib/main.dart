import 'dart:async';
import 'dart:io';

import 'package:api_client/api_client.dart';
import 'package:auth/auth.dart';
import 'package:core/core.dart';
import 'package:design_system/design_system.dart';
import 'package:device_identity/device_identity.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:local_storage/local_storage.dart';
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';
import 'package:realtime/realtime.dart';
import 'package:sync_engine/sync_engine.dart';

import 'src/api_provider.dart';
import 'src/auth_provider.dart';
import 'src/device_provider.dart';
import 'src/i18n/driver_strings.dart';
import 'src/local_database_provider.dart';
import 'src/offline/media_store_provider.dart';
import 'src/offline/sync_providers.dart';
import 'src/push/push_notification_service.dart';
import 'src/router.dart';

/// Backend origin — no `/api/v1` suffix, `AuthApi`'s own paths already carry
/// the full `/api/v1/auth/...` prefix. Defaults to the production server; for
/// local development override it, e.g. for the Android emulator (which cannot
/// resolve `localhost` as the host machine)
/// `--dart-define=API_BASE_URL=http://10.0.2.2:8000`.
const _apiBaseUrl = String.fromEnvironment(
  'API_BASE_URL',
  defaultValue: 'https://lpg.vitessetec.com',
);

/// The `/ws` origin for [_apiBaseUrl] (same host, WebSocket scheme).
String _wsBaseUrl(String apiBaseUrl) => apiBaseUrl
    .replaceFirst('https://', 'wss://')
    .replaceFirst('http://', 'ws://');

/// Driver App entry point.
///
/// Covers the active route (Today), the stop list + delivery history
/// (Deliveries), the driver's profile + logout (Profile), the per-stop
/// workflow (depart → record delivery / proof-of-delivery → payment),
/// background live-location sharing, and FCM push (new-delivery alerts).
/// Reads are cache-first (Phase 26 / ADR-008); the offline write queue
/// (`SyncCoordinator`) lands stage by stage.
///
/// The on-device database and the auth session are both established here,
/// before the first frame, so the rest of the app can assume both are
/// always ready (ADR-008 offline-first; Phase 6 authentication).
/// How proof-of-delivery files are encrypted. On Android and iOS the phone's
/// own AES (through `cryptography_flutter`) is tried first, off the UI thread;
/// if it is unavailable or fails, pure-Dart AES runs on a background isolate,
/// so the app never freezes on a large photo. Elsewhere it is the isolate
/// cipher. Build with `--dart-define=NATIVE_MEDIA_CIPHER=false` to force the
/// isolate cipher (a switch for comparing speed on a real phone).
const _nativeMediaCipher = bool.fromEnvironment(
  'NATIVE_MEDIA_CIPHER',
  defaultValue: true,
);

MediaCipher get _mediaCipher =>
    _nativeMediaCipher && (Platform.isAndroid || Platform.isIOS)
    ? FallbackMediaCipher(
        const InProcessMediaCipher(),
        const IsolateMediaCipher(),
      )
    : const IsolateMediaCipher();

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
        // Only a refusal ends the session; no network or a busy server must
        // not sign the person out.
        onFailure: (failure) =>
            isTransientError(failure) ? throw FailureException(failure) : null,
      );
    },
    onSessionExpired: () => authController.handleSessionExpired(),
    // Requests made while the session is still being restored wait for it.
    waitForSession: () => authController.whenSettled,
  );

  // Device control (ADR-071): plug the phone's identity into the API client
  // *before* anything calls the server — the session restore below is the
  // first request, and it must already carry the install ID.
  late final SyncCoordinator syncCoordinator;
  final deviceControl = await DeviceControl.setUp(
    dio: apiClient.dio,
    appType: 'driver_app',
    // Blocked: sign out. Deliveries not yet sent stay in the local queue.
    onBlocked: () => authController.logout(),
    // Allowed again: send what was saved meanwhile.
    onResumed: () => unawaited(syncCoordinator.syncNow(ignoreBackoff: true)),
  );

  authRepository = ApiAuthRepository(
    authApi: AuthApi(apiClient.dio),
    tokenStorage: tokenStorage,
  );
  authController = AuthController(authRepository);

  // Proof-of-delivery photos and signatures waiting to be sent are encrypted
  // on disk with a key held in secure storage, like the database itself.
  final MediaStore mediaStore = EncryptedMediaStore(
    FileMediaStore(
      Directory(
        p.join((await getApplicationSupportDirectory()).path, 'pod_media'),
      ),
    ),
    loadKey: () => loadOrCreateSecureKeyBytes('driver_app.pod_media_key'),
    cipher: _mediaCipher,
  );

  syncCoordinator = SyncCoordinator(
    database: localDatabase.database,
    apiClient: apiClient,
    // Queued work is sent only under the session of the person who queued it.
    currentOwner: () => authController.state.principal?.userId,
    connectivity: PluginConnectivityMonitor(),
    mediaStore: mediaStore,
    // The agency has not let this phone in: the queue is kept as it is.
    onDeviceRefused: deviceControl.access.reportRefusal,
  );
  syncCoordinator.start();

  // Live updates over `/ws`. Connects lazily on the first subscription (the
  // shell's, once signed in) and reconnects with backoff on its own.
  realtimeClient = RealtimeClient(
    wsBaseUrl: _wsBaseUrl(_apiBaseUrl),
    getAccessToken: () => authRepository.accessToken,
    getInstallId: () => deviceControl.identity.installId,
    // The socket's token was rejected (expired): any authenticated call
    // runs the API client's single 401 -> refresh path, and the socket's
    // own reconnect then picks up the new token.
    onTokenRejected: () async {
      await NotificationApi(apiClient.dio).getUnreadCount();
    },
  );
  _wireRealtimeToAuth(authController, realtimeClient);
  deviceControl.followSession(
    session: authController,
    isAuthenticated: () => authController.state.isAuthenticated,
  );
  // The agency approved or blocked this phone: ask the server where it stands.
  realtimeClient.subscribeToDeviceChanges().listen(
    (_) => unawaited(deviceControl.access.refresh()),
  );

  // Push notifications. Isolated in try/catch: a missing/invalid
  // google-services.json (or a device without Play Services) must not take
  // the whole app down — everything else works fine without push.
  final pushService = PushNotificationService(NotificationApi(apiClient.dio));
  try {
    await Firebase.initializeApp();
    FirebaseMessaging.onBackgroundMessage(firebaseMessagingBackgroundHandler);
    await pushService.init();
    _wirePushRegistrationToAuth(authController, pushService);
  } catch (_) {
    // Best effort: nothing to show the user for this failure.
  }

  // How the app looks (follow the phone, light or dark) is a per-device
  // choice kept outside the per-session tree below, so signing out does not
  // change it.
  const preferences = SecureValueStore();
  final themeMode = await LpgThemeModeController.load(
    read: () => preferences.read('ui.theme_mode'),
    write: (value) => preferences.write('ui.theme_mode', value),
  );

  runApp(
    // A new state tree whenever a signed-in session ends, so the next person
    // on this phone never sees the previous person's cached screens.
    SessionScope(
      authController: authController,
      builder: (context, sessionKey) => ProviderScope(
        key: sessionKey,
        // One quiet retry of a transient failure (the skeleton stays on screen
        // meanwhile), then the error/Retry state. Riverpod's default retries ten
        // times and hides a real error for about half a minute (story 0.4).
        retry: quietRetry,
        overrides: [
          lpgThemeModeControllerProvider.overrideWithValue(themeMode),
          localDatabaseProvider.overrideWithValue(localDatabase),
          authControllerProvider.overrideWithValue(authController),
          deviceControlProvider.overrideWithValue(deviceControl),
          apiClientProvider.overrideWithValue(apiClient),
          syncCoordinatorProvider.overrideWithValue(syncCoordinator),
          mediaStoreProvider.overrideWithValue(mediaStore),
          pushNotificationServiceProvider.overrideWithValue(pushService),
          realtimeClientProvider.overrideWithValue(realtimeClient),
        ],
        child: const DriverApp(),
      ),
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

/// The app's look: one engine, never a hand-built `ThemeData` (story 1.2).
/// The accent stays the brand's flame orange, as before.
const _theme = LpgThemeEngine();

class DriverApp extends ConsumerStatefulWidget {
  const DriverApp({super.key});

  @override
  ConsumerState<DriverApp> createState() => _DriverAppState();
}

class _DriverAppState extends ConsumerState<DriverApp> {
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
    return MaterialApp.router(
      onGenerateTitle: (context) => context.strings.app.title,
      locale: ref.watch(lpgLocaleProvider),
      supportedLocales: driverLaunchLocales,
      localizationsDelegates: driverLocalizationsDelegates,
      theme: _theme.light,
      darkTheme: _theme.dark,
      highContrastTheme: _theme.highContrast,
      highContrastDarkTheme: _theme.highContrast,
      themeMode: ref.watch(lpgThemeModeProvider),
      builder: _theme.builder,
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
    if (authController.state.status == AuthStatus.authenticated) {
      realtimeClient.resume();
    } else {
      unawaited(realtimeClient.pause());
    }
  }

  sync();
  authController.addListener(sync);
}
