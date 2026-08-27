import 'package:auth/auth.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'auth_provider.dart';
import 'features/dashboard/presentation/dashboard_screen.dart';
import 'features/dashboard/presentation/notifications_screen.dart';
import 'features/orders/presentation/invoice_list_screen.dart';
import 'features/orders/presentation/order_detail_screen.dart';
import 'features/orders/presentation/order_tracking_screen.dart';
import 'features/orders/presentation/orders_screen.dart';
import 'package:api_client/api_client.dart';
import 'features/profile/presentation/add_address_screen.dart';
import 'features/profile/presentation/edit_profile_screen.dart';
import 'features/profile/presentation/profile_screen.dart';
import 'features/shell/presentation/app_shell.dart';
import 'features/support/presentation/complaint_detail_screen.dart';
import 'features/support/presentation/raise_complaint_screen.dart';
import 'features/support/presentation/support_screen.dart';
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

      // Still resolving the startup session restore — stay on splash screen.
      if (status == AuthStatus.unknown) {
        if (!splashing) return '/splash';
        return null;
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
        path: '/login',
        name: 'login',
        builder: (context, state) => const LoginScreen(),
      ),
      // Stateful shell route for bottom navigation bar
      StatefulShellRoute.indexedStack(
        builder: (context, state, navigationShell) {
          return AppShell(navigationShell: navigationShell);
        },
        branches: [
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: '/',
                name: 'dashboard',
                builder: (context, state) => const DashboardScreen(),
                routes: [
                  GoRoute(
                    path: 'notifications',
                    name: 'notifications',
                    builder: (context, state) => const NotificationsScreen(),
                  ),
                ],
              ),
            ],
          ),
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: '/orders',
                name: 'orders',
                builder: (context, state) => const OrdersScreen(),
                routes: [
                  GoRoute(
                    path: 'invoices',
                    name: 'invoices',
                    builder: (context, state) => const InvoiceListScreen(),
                  ),
                  GoRoute(
                    path: ':orderId',
                    name: 'order_detail',
                    builder: (context, state) => OrderDetailScreen(
                      orderId: state.pathParameters['orderId']!,
                    ),
                  ),
                  GoRoute(
                    path: ':orderId/track',
                    name: 'order_tracking',
                    builder: (context, state) => OrderTrackingScreen(
                      orderId: state.pathParameters['orderId']!,
                    ),
                  ),
                ],
              ),
            ],
          ),
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: '/support',
                name: 'support',
                builder: (context, state) => const SupportScreen(),
                routes: [
                  GoRoute(
                    path: 'raise',
                    name: 'raise_complaint',
                    builder: (context, state) => const RaiseComplaintScreen(),
                  ),
                  GoRoute(
                    path: ':complaintId',
                    name: 'complaint_detail',
                    builder: (context, state) => ComplaintDetailScreen(
                      complaintId: state.pathParameters['complaintId']!,
                    ),
                  ),
                ],
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
                  GoRoute(
                    path: 'edit',
                    name: 'profile_edit',
                    builder: (context, state) => EditProfileScreen(
                      profile: state.extra as CustomerResponse,
                    ),
                  ),
                  GoRoute(
                    path: 'addresses/new',
                    name: 'profile_address_new',
                    builder: (context, state) =>
                        AddAddressScreen(customerId: state.extra as String),
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
