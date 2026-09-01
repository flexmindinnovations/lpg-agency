import 'package:auth/auth.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'auth_provider.dart';
import 'features/delivery/presentation/active_delivery_screen.dart';
import 'features/delivery/presentation/record_delivery_screen.dart';
import 'features/delivery/presentation/stop_detail_screen.dart';
import 'login_screen.dart';
import 'splash_screen.dart';

/// Routing foundation, with Phase 6's route guards now wired in.
///
/// `redirect:` + `refreshListenable: authController` is the go_router
/// counterpart of the Dashboard's `authGuard`
/// (`frontend/libs/shared/data-access/src/lib/auth.guard.ts`): an
/// unauthenticated (or not-yet-resolved) session is bounced to `/login`,
/// and an authenticated session sitting on `/login` is bounced back to `/`
/// — `refreshListenable` means this re-evaluates immediately on login/
/// logout, not just on the next navigation attempt.
final routerProvider = Provider<GoRouter>((ref) {
  final authController = ref.watch(authControllerProvider);

  return GoRouter(
    initialLocation: '/splash',
    refreshListenable: authController,
    redirect: (context, state) {
      final status = authController.state.status;
      final loggingIn = state.matchedLocation == '/login';
      final splashing = state.matchedLocation == '/splash';

      // Still resolving the startup session restore — stay on the splash
      // screen rather than flashing /login and immediately bouncing back.
      if (status == AuthStatus.unknown) {
        return splashing ? null : '/splash';
      }

      if (status != AuthStatus.authenticated && !loggingIn) return '/login';
      if (status == AuthStatus.authenticated && (loggingIn || splashing)) {
        return '/';
      }
      return null;
    },
    routes: [
      GoRoute(
        path: '/splash',
        name: 'splash',
        builder: (context, state) => const SplashScreen(),
      ),
      GoRoute(
        path: '/',
        name: 'home',
        builder: (context, state) => const ActiveDeliveryScreen(),
        routes: [
          GoRoute(
            path: 'stops/:orderId',
            name: 'stop',
            builder: (context, state) =>
                StopDetailScreen(orderId: state.pathParameters['orderId']!),
            routes: [
              GoRoute(
                path: 'deliver',
                name: 'deliver',
                builder: (context, state) => RecordDeliveryScreen(
                  orderId: state.pathParameters['orderId']!,
                ),
              ),
            ],
          ),
        ],
      ),
      GoRoute(
        path: '/login',
        name: 'login',
        builder: (context, state) => const LoginScreen(),
      ),
    ],
    errorBuilder: (context, state) =>
        Scaffold(body: Center(child: Text('Route not found: ${state.uri}'))),
  );
});
