import 'package:auth/auth.dart';
import 'package:design_system/design_system.dart';
import 'package:device_identity/device_identity.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'auth_provider.dart';
import 'device_provider.dart';
import 'device_strings.dart';
import 'features/approvals/presentation/approvals_screen.dart';
import 'features/cash_book/presentation/cash_book_screen.dart';
import 'features/complaints/presentation/complaint_detail_screen.dart';
import 'features/compliance/presentation/compliance_screen.dart';
import 'features/complaints/presentation/complaints_screen.dart';
import 'features/customers/presentation/add_customer_screen.dart';
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
import 'features/pricing/presentation/pricing_screen.dart';
import 'features/stock/presentation/stock_screen.dart';
import 'login_screen.dart';
import 'splash_screen.dart';

/// Screens that sit above the tab bar (search, alerts, the fleet forms, ...)
/// are pushed on this navigator so the bottom bar hides while they are open.
final _rootNavigatorKey = GlobalKey<NavigatorState>();

/// Phone-width, centred column for full-screen pages on tablets.
Widget _capped(BuildContext context, Widget child) =>
    LpgBreakpoints.isWide(context) ? LpgContentWidth(child: child) : child;

final routerProvider = Provider<GoRouter>((ref) {
  final authController = ref.watch(authControllerProvider);
  final deviceControl = ref.watch(deviceControlProvider);

  return GoRouter(
    navigatorKey: _rootNavigatorKey,
    initialLocation: '/splash',
    refreshListenable: Listenable.merge([authController, deviceControl]),
    redirect: (context, state) {
      final status = authController.state.status;
      final loggingIn = state.matchedLocation == '/login';
      final splashing = state.matchedLocation == '/splash';

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
          strings: adminDeviceStrings,
          suggestedName: deviceControl.suggestedName,
          onSubmit: deviceControl.saveName,
        ),
      ),
      GoRoute(
        path: DeviceRoutes.waiting,
        builder: (context, state) => WaitingForApprovalScreen(
          strings: adminDeviceStrings,
          phoneName: deviceControl.phoneName,
          controller: deviceControl.access,
          onSignOut: () => authController.logout(),
        ),
      ),
      GoRoute(
        path: DeviceRoutes.blocked,
        builder: (context, state) => PhoneBlockedScreen(
          strings: adminDeviceStrings,
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
                    // A full-screen form that is also opened from other
                    // screens (a customer's page, the dashboard), so it
                    // sits above the tab bar rather than inside one tab.
                    parentNavigatorKey: _rootNavigatorKey,
                    builder: (context, state) => _capped(
                      context,
                      CreateOrderScreen(
                        initialCustomerId:
                            state.uri.queryParameters['customer'],
                      ),
                    ),
                  ),
                  GoRoute(
                    path: ':orderId',
                    name: 'order_detail',
                    builder: (context, state) {
                      final id = state.pathParameters['orderId']!;
                      // On a tablet the order opens in the list's right pane.
                      if (LpgBreakpoints.isExpanded(context)) {
                        return OrderListScreen(
                          key: ValueKey('order-pane-$id'),
                          initialSelectedId: id,
                        );
                      }
                      return OrderDetailScreen(orderId: id);
                    },
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
                    builder: (context, state) {
                      final id = state.pathParameters['tripId']!;
                      // On a tablet the trip opens in Dispatch's right pane.
                      if (LpgBreakpoints.isExpanded(context)) {
                        return DispatchScreen(
                          key: ValueKey('trip-pane-$id'),
                          initialSelectedId: id,
                        );
                      }
                      return TripDetailScreen(tripId: id);
                    },
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
        builder: (context, state) => _capped(
          context,
          SearchScreen(initialQuery: state.uri.queryParameters['q'] ?? ''),
        ),
      ),
      GoRoute(
        path: '/alerts',
        name: 'alerts',
        parentNavigatorKey: _rootNavigatorKey,
        builder: (context, state) =>
            _capped(context, const NotificationsScreen()),
      ),
      GoRoute(
        path: '/approvals',
        name: 'approvals',
        parentNavigatorKey: _rootNavigatorKey,
        builder: (context, state) => _capped(context, const ApprovalsScreen()),
      ),
      GoRoute(
        path: '/pricing',
        name: 'pricing',
        parentNavigatorKey: _rootNavigatorKey,
        builder: (context, state) => _capped(context, const PricingScreen()),
      ),
      GoRoute(
        path: '/compliance',
        name: 'compliance',
        parentNavigatorKey: _rootNavigatorKey,
        builder: (context, state) => _capped(context, const ComplianceScreen()),
      ),
      GoRoute(
        path: '/stock',
        name: 'stock',
        parentNavigatorKey: _rootNavigatorKey,
        builder: (context, state) => _capped(
          context,
          StockScreen(initialGodownId: state.uri.queryParameters['godown']),
        ),
      ),
      GoRoute(
        path: '/cash-book',
        name: 'cash_book',
        parentNavigatorKey: _rootNavigatorKey,
        builder: (context, state) => _capped(context, const CashBookScreen()),
      ),
      GoRoute(
        path: '/profile',
        name: 'profile',
        parentNavigatorKey: _rootNavigatorKey,
        builder: (context, state) => _capped(context, const ProfileScreen()),
      ),
      GoRoute(
        path: '/customers',
        name: 'customers',
        parentNavigatorKey: _rootNavigatorKey,
        builder: (context, state) => const CustomersScreen(),
        routes: [
          GoRoute(
            path: 'new',
            name: 'customer_new',
            builder: (context, state) =>
                _capped(context, const AddCustomerScreen()),
          ),
          GoRoute(
            path: ':customerId',
            name: 'customer_detail',
            builder: (context, state) => _capped(
              context,
              CustomerDetailScreen(
                customerId: state.pathParameters['customerId']!,
              ),
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
            builder: (context, state) => _capped(
              context,
              ComplaintDetailScreen(
                complaintId: state.pathParameters['complaintId']!,
              ),
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
            builder: (context, state) => _capped(
              context,
              InvoiceDetailScreen(
                invoiceId: state.pathParameters['invoiceId']!,
              ),
            ),
          ),
        ],
      ),
      GoRoute(
        path: '/fleet',
        name: 'fleet',
        parentNavigatorKey: _rootNavigatorKey,
        builder: (context, state) => _capped(
          context,
          FleetScreen(
            initialTab: state.uri.queryParameters['tab'] == 'vans' ? 1 : 0,
          ),
        ),
        routes: [
          GoRoute(
            path: 'driver-new',
            name: 'fleet_driver_new',
            builder: (context, state) =>
                _capped(context, const DriverFormScreen()),
          ),
          GoRoute(
            path: 'van-new',
            name: 'fleet_vehicle_new',
            builder: (context, state) =>
                _capped(context, const VehicleFormScreen()),
          ),
        ],
      ),
    ],
    errorBuilder: (context, state) =>
        Scaffold(body: Center(child: Text('Route not found: ${state.uri}'))),
  );
});
