import 'package:auth/auth.dart';
import 'package:design_system/design_system.dart';
import 'package:device_identity/device_identity.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'auth_provider.dart';
import 'device_provider.dart';
import 'device_strings.dart';
import 'features/cash_handover/presentation/cash_handover_screen.dart';
import 'features/delivery/presentation/deliveries_screen.dart';
import 'features/delivery/presentation/record_delivery_screen.dart';
import 'features/delivery/presentation/stop_detail_screen.dart';
import 'features/delivery/presentation/today_screen.dart';
import 'features/notifications/presentation/notifications_screen.dart';
import 'features/profile/presentation/profile_screen.dart';
import 'features/shell/presentation/app_shell.dart';
import 'features/sync/presentation/sync_status_screen.dart';
import 'features/van_load/presentation/van_load_screen.dart';
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
  final deviceControl = ref.watch(deviceControlProvider);

  return GoRouter(
    initialLocation: '/splash',
    refreshListenable: Listenable.merge([authController, deviceControl]),
    redirect: (context, state) {
      final status = authController.state.status;
      final loggingIn = state.matchedLocation == '/login';
      final splashing = state.matchedLocation == '/splash';

      // Still resolving the startup session restore — stay on the splash
      // screen rather than flashing /login and immediately bouncing back.
      if (status == AuthStatus.unknown) {
        return splashing ? null : '/splash';
      }

      // A phone that is unnamed, waiting for approval or blocked (ADR-071)
      // is shown its own screen before anything else.
      final deviceRoute = deviceControl.redirect(
        location: state.matchedLocation,
        authenticated: status == AuthStatus.authenticated,
      );
      if (deviceRoute != null) return deviceRoute;
      if (DeviceRoutes.all.contains(state.matchedLocation)) return null;

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
        path: DeviceRoutes.name,
        builder: (context, state) => NameThisPhoneScreen(
          strings: driverDeviceStrings,
          suggestedName: deviceControl.suggestedName,
          onSubmit: deviceControl.saveName,
        ),
      ),
      GoRoute(
        path: DeviceRoutes.waiting,
        builder: (context, state) => WaitingForApprovalScreen(
          strings: driverDeviceStrings,
          phoneName: deviceControl.phoneName,
          controller: deviceControl.access,
          onSignOut: () => authController.logout(),
        ),
      ),
      GoRoute(
        path: DeviceRoutes.blocked,
        builder: (context, state) => PhoneBlockedScreen(
          strings: driverDeviceStrings,
          onTryAgain: deviceControl.tryAgain,
        ),
      ),
      GoRoute(
        path: '/login',
        name: 'login',
        builder: (context, state) => const LpgContentWidth(
          maxWidth: LpgBreakpoints.formMaxWidth,
          child: LoginScreen(),
        ),
      ),
      // One-off tasks reached from more than one tab (Today's nudges, the
      // Deliveries history) sit above the shell and are *pushed*, so Back
      // returns to wherever the driver came from and no tab keeps them in
      // its stack. Nested under Deliveries, the cash handover reopened
      // every time the Deliveries tab was tapped (DR-08).
      GoRoute(
        path: '/routes/:routeId/cash-handover',
        name: 'cashHandover',
        builder: (context, state) => LpgContentWidth(
          child: CashHandoverScreen(routeId: state.pathParameters['routeId']!),
        ),
      ),
      GoRoute(
        path: '/routes/:routeId/load',
        name: 'vanLoad',
        builder: (context, state) => LpgContentWidth(
          child: VanLoadScreen(routeId: state.pathParameters['routeId']!),
        ),
      ),
      StatefulShellRoute.indexedStack(
        builder: (context, state, navigationShell) =>
            AppShell(navigationShell: navigationShell),
        branches: [
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: '/',
                name: 'home',
                builder: (context, state) => const TodayScreen(),
              ),
            ],
          ),
          // The delivery drill-in (stop detail → record delivery) lives
          // under the Deliveries branch so the bottom bar stays visible;
          // it's reached from the Today cards and the Alerts inbox with
          // `goNamed` (a cross-branch navigate), which builds the full
          // `[Deliveries, …]` back stack.
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: '/deliveries',
                name: 'deliveries',
                builder: (context, state) => const DeliveriesScreen(),
                routes: [
                  GoRoute(
                    path: 'stops/:orderId',
                    name: 'stop',
                    builder: (context, state) => StopDetailScreen(
                      orderId: state.pathParameters['orderId']!,
                    ),
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
            ],
          ),
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: '/alerts',
                name: 'alerts',
                builder: (context, state) => const NotificationsScreen(),
              ),
            ],
          ),
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: '/profile',
                name: 'profile',
                builder: (context, state) => const ProfileScreen(),
                routes: [
                  // Offline-queue health — reached from the Profile row.
                  GoRoute(
                    path: 'sync',
                    name: 'sync',
                    builder: (context, state) => const SyncStatusScreen(),
                  ),
                ],
              ),
            ],
          ),
        ],
      ),
    ],
    errorBuilder: (context, state) =>
        Scaffold(body: Center(child: Text('Route not found: ${state.uri}'))),
  );
});
