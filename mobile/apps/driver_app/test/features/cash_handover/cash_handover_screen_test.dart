import 'dart:convert';

import 'package:api_client/api_client.dart';
import 'package:design_system/design_system.dart';
import 'package:dio/dio.dart';
import 'package:driver_app/src/features/cash_handover/data/cash_handover_provider.dart';
import 'package:driver_app/src/features/cash_handover/presentation/cash_handover_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/offline_harness.dart';

RouteCashHandover _view({
  String status = 'completed',
  double expected = 905.50,
  int cashStops = 1,
  CashHandover? handover,
}) => RouteCashHandover(
  routeId: 'route-1',
  driverId: 'drv-1',
  routeStatus: status,
  routeDate: DateTime(2026, 9, 1),
  expectedAmount: expected,
  cashStopCount: cashStops,
  handover: handover,
);

CashHandover _handover({double actual = 900, double shortfall = 5.50}) =>
    CashHandover(
      id: 'csh-1',
      handoverNumber: 'CSH000003',
      driverId: 'drv-1',
      routeId: 'route-1',
      expectedAmount: 905.50,
      actualAmount: actual,
      shortfall: shortfall,
      declaredBy: 'user-1',
      declaredAt: DateTime(2026, 9, 2),
    );

Widget _host(ProviderContainer container) => UncontrolledProviderScope(
  container: container,
  child: MaterialApp(
    theme: LpgTheme.light,
    home: const CashHandoverScreen(routeId: 'route-1'),
  ),
);

Future<void> _pump(WidgetTester tester, ProviderContainer container) async {
  tester.view.physicalSize = const Size(1000, 2200);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.reset);
  await tester.pumpWidget(_host(container));
  await tester.pumpAndSettle();
}

/// The amount-handed-over field (the reason field, when shown, comes after).
Finder get _amountField => find.byType(TextFormField).first;

/// Stateful fake: `/for-route` returns the pending view until a POST lands,
/// then the declared one — so a real declare flow flips the screen to the
/// receipt on its own.
class _CashAdapter implements HttpClientAdapter {
  Map<String, dynamic>? declareBody;
  bool declared = false;

  @override
  Future<ResponseBody> fetch(RequestOptions options, _, _) async {
    if (options.method == 'POST' && options.path == '/api/v1/cash-handovers') {
      declareBody = options.data as Map<String, dynamic>;
      declared = true;
      return _json({
        'id': 'csh-1',
        'handover_number': 'CSH000003',
        'driver_id': 'drv-1',
        'route_id': 'route-1',
        'expected_amount': '905.50',
        'actual_amount': '900.00',
        'shortfall': '5.50',
        'declared_by': 'user-1',
        'declared_at': '2026-09-02T00:00:00Z',
      }, 201);
    }
    if (options.path.startsWith('/api/v1/cash-handovers/for-route/')) {
      return _json({
        'route_id': 'route-1',
        'driver_id': 'drv-1',
        'route_status': 'completed',
        'route_date': '2026-09-01T00:00:00Z',
        'expected_amount': '905.50',
        'cash_stop_count': 1,
        'handover': declared
            ? {
                'id': 'csh-1',
                'handover_number': 'CSH000003',
                'driver_id': 'drv-1',
                'route_id': 'route-1',
                'expected_amount': '905.50',
                'actual_amount': '900.00',
                'shortfall': '5.50',
                'declared_by': 'user-1',
                'declared_at': '2026-09-02T00:00:00Z',
              }
            : null,
      }, 200);
    }
    // routeHistoryProvider / pendingCashHandoverProvider invalidations.
    return _json({'items': <dynamic>[]}, 200);
  }

  @override
  void close({bool force = false}) {}
}

ResponseBody _json(Object body, int status) => ResponseBody.fromString(
  jsonEncode(body),
  status,
  headers: {
    Headers.contentTypeHeader: [Headers.jsonContentType],
  },
);

void main() {
  group('CashHandoverScreen', () {
    testWidgets('shows the expected amount and a declare action', (
      tester,
    ) async {
      final container = ProviderContainer(
        overrides: [
          routeCashHandoverProvider.overrideWith(
            (ref, id) async => _view(expected: 1811.00, cashStops: 2),
          ),
        ],
      );
      addTearDown(container.dispose);

      await _pump(tester, container);

      expect(
        find.text('₹1,811.00'),
        findsWidgets,
      ); // the headline and the Cash row
      expect(find.textContaining('2 cash deliveries'), findsOneWidget);
      expect(
        find.widgetWithText(LpgButton, 'Declare handover'),
        findsOneWidget,
      );
    });

    testWidgets('starts at the cash expected, with no note counter', (
      tester,
    ) async {
      final container = ProviderContainer(
        overrides: [
          routeCashHandoverProvider.overrideWith(
            (ref, id) async => _view(expected: 905.50),
          ),
        ],
      );
      addTearDown(container.dispose);

      await _pump(tester, container);

      expect(find.text('Count the cash'), findsNothing);
      expect(find.byTooltip('Increase'), findsNothing);
      // The amount is already what was collected, so there is nothing to
      // type for a driver who hands it all over.
      expect(
        tester.widget<TextFormField>(_amountField).controller!.text,
        '905.50',
      );
      expect(find.textContaining('Matches the expected'), findsOneWidget);
      // Cash and UPI are kept apart: UPI went straight to the agency.
      expect(find.text('Cash'), findsOneWidget);
      expect(find.text('UPI'), findsOneWidget);
      expect(find.textContaining('Nothing to hand over'), findsOneWidget);
    });

    testWidgets('reports the difference and asks why when it is a rupee or '
        'more', (tester) async {
      final container = ProviderContainer(
        overrides: [
          routeCashHandoverProvider.overrideWith(
            (ref, id) async => _view(expected: 1000),
          ),
        ],
      );
      addTearDown(container.dispose);

      await _pump(tester, container);

      await tester.enterText(_amountField, '900');
      await tester.pump();
      expect(find.text('Short by ₹100.00'), findsOneWidget);
      expect(find.textContaining('Why does it differ?'), findsOneWidget);

      await tester.enterText(_amountField, '1000');
      await tester.pump();
      expect(find.textContaining('Matches the expected'), findsOneWidget);
      expect(find.textContaining('Why does it differ?'), findsNothing);

      await tester.enterText(_amountField, '1100');
      await tester.pump();
      expect(find.text('Over by ₹100.00'), findsOneWidget);
    });

    testWidgets('rounding under a rupee needs no reason', (tester) async {
      final container = ProviderContainer(
        overrides: [
          routeCashHandoverProvider.overrideWith(
            (ref, id) async => _view(expected: 905.50),
          ),
        ],
      );
      addTearDown(container.dispose);

      await _pump(tester, container);

      await tester.enterText(_amountField, '905');
      await tester.pump();

      // Rs 905 against Rs 905.50: close enough to need no reason, but not
      // a match, and the screen must not say it is.
      expect(find.textContaining('Matches the expected'), findsNothing);
      expect(find.textContaining('Short by ₹0.50'), findsOneWidget);
      expect(find.textContaining('no reason is needed'), findsOneWidget);
      expect(find.textContaining('Why does it differ?'), findsNothing);
    });

    testWidgets('a route still in progress cannot be reconciled', (
      tester,
    ) async {
      final container = ProviderContainer(
        overrides: [
          routeCashHandoverProvider.overrideWith(
            (ref, id) async => _view(status: 'in_progress'),
          ),
        ],
      );
      addTearDown(container.dispose);

      await _pump(tester, container);

      expect(find.textContaining('still in progress'), findsOneWidget);
      expect(find.widgetWithText(LpgButton, 'Declare handover'), findsNothing);
    });

    testWidgets('a declared handover renders the receipt', (tester) async {
      final container = ProviderContainer(
        overrides: [
          routeCashHandoverProvider.overrideWith(
            (ref, id) async => _view(handover: _handover()),
          ),
        ],
      );
      addTearDown(container.dispose);

      await _pump(tester, container);

      expect(find.text('CSH000003'), findsOneWidget);
      expect(find.text('SHORT'), findsOneWidget);
      expect(find.text('₹5.50'), findsOneWidget); // shortfall row
      expect(find.textContaining('has been reconciled'), findsOneWidget);
      expect(find.byType(TextFormField), findsNothing);
    });

    testWidgets('declaring queues the handover, then shows the receipt once '
        'it syncs', (tester) async {
      final adapter = _CashAdapter();
      final harness = OfflineHarness(
        ApiClient(baseUrl: 'https://api.test')..dio.httpClientAdapter = adapter,
      );
      addTearDown(harness.dispose);
      final container = ProviderContainer(overrides: harness.overrides);
      addTearDown(container.dispose);

      await _pump(tester, container);

      await tester.enterText(_amountField, '900');
      await tester.pump();
      await tester.enterText(find.byType(TextFormField).last, 'Gave change');
      await tester.pump();
      await tester.tap(find.widgetWithText(LpgButton, 'Declare handover'));
      await tester.pumpAndSettle();

      // Confirm dialog.
      expect(find.text('Confirm cash handover'), findsOneWidget);
      await tester.tap(find.widgetWithText(LpgButton, 'Confirm'));
      await tester.pumpAndSettle();

      // The op was queued with the right body...
      final ops = await harness.ops();
      expect(ops.single.type, 'cash_handover_declare');
      expect(jsonDecode(ops.single.payload)['body'], {
        'driver_id': 'drv-1',
        'route_id': 'route-1',
        'actual_amount': '900.00',
        'variance_reason': 'Gave change',
      });
      // ...synced against the stub, and the screen has caught up to the
      // receipt.
      expect(adapter.declared, isTrue);
      expect(find.text('CSH000003'), findsOneWidget);
      expect(find.byType(TextFormField), findsNothing);
    });
  });
}
