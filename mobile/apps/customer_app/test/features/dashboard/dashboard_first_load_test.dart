// Story 0.4 for the Customer app: the home tab keeps its placeholders until the
// first answer, retries a transient failure once without showing an error,
// shows the error only if the retry also fails, and keeps what it has on
// screen when a refresh fails.
import 'package:api_client/api_client.dart';
import 'package:core/core.dart';
import 'package:customer_app/src/features/dashboard/data/ledger_provider.dart';
import 'package:customer_app/src/features/dashboard/data/notifications_provider.dart';
import 'package:customer_app/src/features/dashboard/presentation/dashboard_screen.dart';
import 'package:customer_app/src/features/orders/data/orders_provider.dart';
import 'package:customer_app/src/features/profile/data/profile_provider.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

const _offline = FailureException(
  Failure(
    message: 'Cannot reach the server.',
    errorCode: 'NETWORK_UNAVAILABLE',
  ),
);

const _ledger = CylinderLedgerResponse(
  customerId: 'c1',
  balances: [CylinderLedgerBalanceItem(cylinderTypeId: 't1', quantity: 3)],
);

/// A provider body that plays [steps] in order (the last repeats): a value is
/// returned, anything thrown is thrown.
Future<T> Function(Ref) _script<T>(List<Object> steps, {List<int>? counter}) {
  var calls = 0;
  return (ref) async {
    final step = steps[calls.clamp(0, steps.length - 1)];
    calls++;
    counter?.add(calls);
    if (step is T) return step as T;
    throw step;
  };
}

Future<void> _pump(
  WidgetTester tester, {
  required List<Object> ledger,
  List<Object> orders = const [<OrderResponse>[]],
}) async {
  tester.view.physicalSize = const Size(1200, 4000);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.reset);
  await tester.pumpWidget(
    ProviderScope(
      retry: quietRetry,
      overrides: [
        ledgerProvider.overrideWith(_script<CylinderLedgerResponse?>(ledger)),
        ordersProvider.overrideWith(_script<List<OrderResponse>>(orders)),
        profileProvider.overrideWith((ref) => null),
        unreadNotificationCountProvider.overrideWith((ref) => 0),
      ],
      child: MaterialApp(theme: LpgTheme.light, home: const DashboardScreen()),
    ),
  );
}

const _ledgerError = 'Balance unavailable right now';
// The recent-orders section shows the friendly banner for a lost connection.
const _ordersError = 'No internet';
const _after = Duration(milliseconds: 100);

Future<void> _pastRetryDelay(WidgetTester tester) async {
  await tester.pump(quietRetryDelay + _after);
  await tester.pump(_after);
}

OrderResponse _order(String id, String status) => OrderResponse(
  id: id,
  tenantId: 't',
  branchId: 'b',
  customerId: 'c',
  addressId: 'a',
  deliveryAddress: const DeliveryAddressPayload(addressLine: 'x'),
  status: status,
  bookingSource: 'mobile_app',
  requestedDate: DateTime(2026, 11, 1),
  metadata: const {},
  lines: const [],
);

void main() {
  testWidgets('the balance hero counts orders on the way and placed', (
    tester,
  ) async {
    await _pump(
      tester,
      ledger: [_ledger],
      orders: [
        [
          _order('o1', 'out_for_delivery'),
          _order('o2', 'delivered'),
          _order('o3', 'delivered'),
        ],
      ],
    );
    await tester.pumpAndSettle();

    expect(find.byType(LpgHeroStats), findsOneWidget);
    expect(find.text('On the way'), findsOneWidget);
    expect(find.text('Orders placed'), findsOneWidget);
    expect(find.text('3'), findsWidgets);
  });

  testWidgets('no order counts in the hero before the first order', (
    tester,
  ) async {
    await _pump(tester, ledger: [_ledger]);
    await tester.pumpAndSettle();

    expect(find.byType(LpgHeroStats), findsNothing);
  });

  testWidgets('first request fails, retry succeeds: no error is ever shown', (
    tester,
  ) async {
    await _pump(
      tester,
      ledger: [_offline, _ledger],
      orders: [_offline, <OrderResponse>[]],
    );

    await tester.pump(_after);
    expect(find.text(_ledgerError), findsNothing);
    expect(find.text(_ordersError), findsNothing);
    expect(find.byType(CircularProgressIndicator), findsOneWidget);
    expect(find.byType(LpgSkeletonList), findsOneWidget);

    await _pastRetryDelay(tester);
    await tester.pump(const Duration(seconds: 2));
    expect(find.text(_ledgerError), findsNothing);
    expect(find.text(_ordersError), findsNothing);
    expect(find.text('Across 1 cylinder type'), findsOneWidget);
    expect(find.text('No recent orders'), findsOneWidget);
  });

  testWidgets('shows the error only when the retry fails as well', (
    tester,
  ) async {
    await _pump(tester, ledger: [_offline], orders: [_offline]);

    await tester.pump(_after);
    expect(find.text(_ledgerError), findsNothing);
    expect(find.text(_ordersError), findsNothing);

    await _pastRetryDelay(tester);
    expect(find.text(_ledgerError), findsOneWidget);
    expect(find.text(_ordersError), findsOneWidget);
  });

  testWidgets('does not retry a refusal that will not change', (tester) async {
    final calls = <int>[];
    tester.view.physicalSize = const Size(1200, 4000);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);
    await tester.pumpWidget(
      ProviderScope(
        retry: quietRetry,
        overrides: [
          ledgerProvider.overrideWith(
            _script<CylinderLedgerResponse?>([
              const FailureException(
                Failure(message: 'No.', errorCode: 'FORBIDDEN'),
              ),
            ], counter: calls),
          ),
          ordersProvider.overrideWith((ref) => <OrderResponse>[]),
          profileProvider.overrideWith((ref) => null),
          unreadNotificationCountProvider.overrideWith((ref) => 0),
        ],
        child: MaterialApp(
          theme: LpgTheme.light,
          home: const DashboardScreen(),
        ),
      ),
    );

    await tester.pump(_after);
    expect(find.text(_ledgerError), findsOneWidget);
    await tester.pump(quietRetryDelay * 2);
    expect(calls, [1]);
  });

  testWidgets('a failed refresh keeps the balance that is already shown', (
    tester,
  ) async {
    await _pump(
      tester,
      ledger: [_ledger, _offline],
      orders: [<OrderResponse>[]],
    );
    await tester.pump(_after);
    await tester.pump(const Duration(seconds: 2));
    expect(find.text('Across 1 cylinder type'), findsOneWidget);

    final container = ProviderScope.containerOf(
      tester.element(find.byType(DashboardScreen)),
    );
    container.invalidate(ledgerProvider);
    await tester.pump(_after);
    expect(find.text('Across 1 cylinder type'), findsOneWidget);

    await _pastRetryDelay(tester);
    expect(find.text('Across 1 cylinder type'), findsOneWidget);
    expect(find.text(_ledgerError), findsNothing);
  });
}
