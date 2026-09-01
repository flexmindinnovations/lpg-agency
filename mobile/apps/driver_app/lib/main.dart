import 'package:api_client/api_client.dart';
import 'package:auth/auth.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:local_storage/local_storage.dart';
import 'package:sync_engine/sync_engine.dart';

import 'src/api_provider.dart';
import 'src/auth_provider.dart';
import 'src/local_database_provider.dart';
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
/// Shell only. Assigned deliveries, route, vehicle inventory, proof of
/// delivery and payment collection each arrive in their own phase.
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

  runApp(
    ProviderScope(
      overrides: [
        localDatabaseProvider.overrideWithValue(localDatabase),
        authControllerProvider.overrideWithValue(authController),
        apiClientProvider.overrideWithValue(apiClient),
      ],
      child: const DriverApp(),
    ),
  );
}

class DriverApp extends ConsumerWidget {
  const DriverApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
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
