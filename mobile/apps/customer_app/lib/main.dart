import 'package:api_client/api_client.dart';
import 'package:auth/auth.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'src/auth_provider.dart';
import 'src/router.dart';

/// Backend origin — no `/api/v1` suffix, `AuthApi`'s own paths already carry
/// the full `/api/v1/auth/...` prefix. Override for a real device or an
/// Android emulator (which cannot resolve `localhost` as the host machine)
/// with `--dart-define=API_BASE_URL=http://10.0.2.2:8000`.
const _apiBaseUrl = String.fromEnvironment(
  'API_BASE_URL',
  defaultValue: 'http://localhost:8000',
);

/// Customer App entry point.
///
/// Shell only beyond authentication. Registration, booking, tracking,
/// payments and complaints are each built in their own phase, behind their
/// own plan.
///
/// `WidgetsFlutterBinding.ensureInitialized()` is required here now (unlike
/// the original Phase 5 shell) — `SecureTokenStorage`'s startup session
/// restore touches a platform channel shortly after `runApp` returns.
void main() {
  WidgetsFlutterBinding.ensureInitialized();

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

  runApp(
    ProviderScope(
      overrides: [authControllerProvider.overrideWithValue(authController)],
      child: const CustomerApp(),
    ),
  );
}

class CustomerApp extends ConsumerWidget {
  const CustomerApp({super.key});

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
