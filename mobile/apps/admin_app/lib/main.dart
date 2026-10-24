// LPG Agency Admin Main Entry Point
import 'package:api_client/api_client.dart';
import 'package:auth/auth.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'src/auth_provider.dart';
import 'src/providers.dart';
import 'src/router.dart';

const _apiBaseUrl = String.fromEnvironment(
  'API_BASE_URL',
  defaultValue: 'https://lpg.vitessetec.com',
);

void main() async {
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
      overrides: [
        authControllerProvider.overrideWithValue(authController),
        apiClientProvider.overrideWithValue(apiClient),
      ],
      child: const AdminApp(),
    ),
  );
}

class AdminApp extends ConsumerWidget {
  const AdminApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
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
