import 'package:auth/auth.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'auth_provider.dart';
import 'features/approvals/presentation/approvals_screen.dart';
import 'features/cash_book/presentation/cash_book_screen.dart';
import 'features/complaints/presentation/complaint_detail_screen.dart';
import 'features/complaints/presentation/complaints_screen.dart';
import 'features/customers/presentation/customer_detail_screen.dart';
import 'features/customers/presentation/customers_screen.dart';
import 'features/dashboard/presentation/dashboard_screen.dart';
import 'features/dispatch/presentation/dispatch_screen.dart';
import 'features/dispatch/presentation/trip_detail_screen.dart';
import 'features/fleet/presentation/driver_form_screen.dart';
import 'features/fleet/presentation/fleet_screen.dart';
import 'features/fleet/presentation/vehicle_form_screen.dart';
import 'features/invoices/presentation/invoice_detail_screen.dart';
import 'features/invoices/presentation/invoices_screen.dart';
import 'features/more/presentation/more_screen.dart';
import 'features/notifications/presentation/notifications_screen.dart';
import 'features/orders/presentation/create_order_screen.dart';
import 'features/orders/presentation/order_detail_screen.dart';
import 'features/orders/presentation/order_list_screen.dart';
import 'features/profile/presentation/profile_screen.dart';
import 'features/search/presentation/search_screen.dart';
import 'features/shell/presentation/app_shell.dart';
import 'features/stock/presentation/stock_screen.dart';
import 'login_screen.dart';
import 'splash_screen.dart';

/// Screens that sit above the tab bar (search, alerts, the fleet forms, ...)
/// are pushed on this navigator so the bottom bar hides while they are open.
final _rootNavigatorKey = GlobalKey<NavigatorState>();

final routerProvider = Provider<GoRouter>((ref) {
  final authController = ref.watch(authControllerProvider);

  return GoRouter(
    navigatorKey: _rootNavigatorKey,
    initialLocation: '/splash',
    refreshListenable: authController,
    redirect: (context, state) {
      final status = authController.state.status;
      final loggingIn = state.matchedLocation == '/login';
      final splashing = state.matchedLocation == '/splash';

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
        path: '/login',
        name: 'login',
        builder: (context, state) => const LpgContentWidth(
          maxWidth: LpgBreakpoints.formMaxWidth,
          paintCanvas: true,
          child: LoginScreen(),
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
                name: 'dashboard',
                builder: (context, state) => const DashboardScreen(),
              ),
            ],
          ),
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: '/orders',
                name: 'orders',
                builder: (context, state) => OrderListScreen(
                  key: ValueKey(state.uri.query),
                  initialFilter: state.uri.queryParameters['filter'],
                  initialSearch: state.uri.queryParameters['q'],
                ),
                routes: [
                  GoRoute(
                    path: 'new',
                    name: 'order_new',
                    builder: (context, state) => CreateOrderScreen(
                      initialCustomerId: state.uri.queryParameters['customer'],
                    ),
                  ),
                  GoRoute(
                    path: ':orderId',
                    name: 'order_detail',
                    builder: (context, state) => OrderDetailScreen(
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
                path: '/dispatch',
                name: 'dispatch',
                builder: (context, state) => const DispatchScreen(),
                routes: [
                  GoRoute(
                    path: 'trip/:tripId',
                    name: 'trip_detail',
                    builder: (context, state) => TripDetailScreen(
                      tripId: state.pathParameters['tripId']!,
                    ),
                  ),
                ],
              ),
            ],
          ),
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: '/more',
                name: 'more',
                builder: (context, state) => const MoreScreen(),
              ),
            ],
          ),
        ],
      ),
      GoRoute(
        path: '/search',
        name: 'search',
        parentNavigatorKey: _rootNavigatorKey,
        builder: (context, state) =>
            SearchScreen(initialQuery: state.uri.queryParameters['q'] ?? ''),
      ),
      GoRoute(
        path: '/alerts',
        name: 'alerts',
        parentNavigatorKey: _rootNavigatorKey,
        builder: (context, state) => const NotificationsScreen(),
      ),
      GoRoute(
        path: '/approvals',
        name: 'approvals',
        parentNavigatorKey: _rootNavigatorKey,
        builder: (context, state) => const ApprovalsScreen(),
      ),
      GoRoute(
        path: '/stock',
        name: 'stock',
        parentNavigatorKey: _rootNavigatorKey,
        builder: (context, state) =>
            StockScreen(initialGodownId: state.uri.queryParameters['godown']),
      ),
      GoRoute(
        path: '/cash-book',
        name: 'cash_book',
        parentNavigatorKey: _rootNavigatorKey,
        builder: (context, state) => const CashBookScreen(),
      ),
      GoRoute(
        path: '/profile',
        name: 'profile',
        parentNavigatorKey: _rootNavigatorKey,
        builder: (context, state) => const ProfileScreen(),
      ),
      GoRoute(
        path: '/customers',
        name: 'customers',
        parentNavigatorKey: _rootNavigatorKey,
        builder: (context, state) => const CustomersScreen(),
        routes: [
          GoRoute(
            path: ':customerId',
            name: 'customer_detail',
            builder: (context, state) => CustomerDetailScreen(
              customerId: state.pathParameters['customerId']!,
            ),
          ),
        ],
      ),
      GoRoute(
        path: '/complaints',
        name: 'complaints',
        parentNavigatorKey: _rootNavigatorKey,
        builder: (context, state) => ComplaintsScreen(
          key: ValueKey(state.uri.query),
          customerId: state.uri.queryParameters['customer'],
          initialStatus: state.uri.queryParameters['status'],
        ),
        routes: [
          GoRoute(
            path: ':complaintId',
            name: 'complaint_detail',
            builder: (context, state) => ComplaintDetailScreen(
              complaintId: state.pathParameters['complaintId']!,
            ),
          ),
        ],
      ),
      GoRoute(
        path: '/invoices',
        name: 'invoices',
        parentNavigatorKey: _rootNavigatorKey,
        builder: (context, state) => InvoicesScreen(
          key: ValueKey(state.uri.query),
          customerId: state.uri.queryParameters['customer'],
          initialStatus: state.uri.queryParameters['status'],
        ),
        routes: [
          GoRoute(
            path: ':invoiceId',
            name: 'invoice_detail',
            builder: (context, state) => InvoiceDetailScreen(
              invoiceId: state.pathParameters['invoiceId']!,
            ),
          ),
        ],
      ),
      GoRoute(
        path: '/fleet',
        name: 'fleet',
        parentNavigatorKey: _rootNavigatorKey,
        builder: (context, state) => FleetScreen(
          initialTab: state.uri.queryParameters['tab'] == 'vans' ? 1 : 0,
        ),
        routes: [
          GoRoute(
            path: 'driver-new',
            name: 'fleet_driver_new',
            builder: (context, state) => const DriverFormScreen(),
          ),
          GoRoute(
            path: 'van-new',
            name: 'fleet_vehicle_new',
            builder: (context, state) => const VehicleFormScreen(),
          ),
        ],
      ),
    ],
    errorBuilder: (context, state) =>
        Scaffold(body: Center(child: Text('Route not found: ${state.uri}'))),
  );
});
