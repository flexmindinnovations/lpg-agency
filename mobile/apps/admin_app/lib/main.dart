// LPG Agency Admin Main Entry Point
import 'dart:async';

import 'package:api_client/api_client.dart';
import 'package:auth/auth.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:realtime/realtime.dart';

import 'src/auth_provider.dart';
import 'src/providers.dart';
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

  runApp(
    ProviderScope(
      // Riverpod 3 retries failed providers with backoff and keeps them in
      // the loading state meanwhile, so errors never reached the screens'
      // error/Retry states. Fail fast; the user retries explicitly.
      retry: (_, _) => null,
      overrides: [
        authControllerProvider.overrideWithValue(authController),
        apiClientProvider.overrideWithValue(apiClient),
        realtimeClientProvider.overrideWithValue(realtimeClient),
      ],
      child: const AdminApp(),
    ),
  );
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
