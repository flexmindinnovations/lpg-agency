import 'package:admin_app/src/features/cash_book/data/cash_book_provider.dart';
import 'package:admin_app/src/features/cash_book/presentation/cash_book_screen.dart';
import 'package:api_client/api_client.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

CashBook _book({List<CashBookCollection> collections = const []}) => CashBook(
  date: '2026-10-30',
  collections: collections,
  totalCollected: collections.fold(0, (sum, c) => sum + c.amount),
  handoverCount: 2,
  expectedTotal: 5000,
  handedOverTotal: 4900,
  shortfallTotal: 100,
  excessTotal: 0,
  acceptedTotal: 3000,
  disputedTotal: 0,
  pendingTotal: 1900,
  pendingCount: 1,
  cashInHandTotal: 800,
);

Widget _app({
  required List<String> requestedDays,
  CashInHand held = const CashInHand(totalCash: 0, drivers: []),
  List<CashBookCollection> collections = const [],
}) => ProviderScope(
  overrides: [
    cashBookProvider.overrideWith((ref, day) async {
      requestedDays.add(day);
      return _book(collections: collections);
    }),
    cashInHandProvider.overrideWith((ref) async => held),
  ],
  child: MaterialApp(theme: LpgTheme.light, home: const CashBookScreen()),
);

Future<void> _tallScreen(WidgetTester tester) async {
  tester.view.physicalSize = const Size(800, 3200);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.reset);
}

void main() {
  test('asks the API for a day as YYYY-MM-DD', () {
    expect(cashBookDay(DateTime(2026, 3, 7)), '2026-03-07');
    expect(cashBookDay(DateTime(2026, 11, 30)), '2026-11-30');
  });

  group('CashBookScreen', () {
    testWidgets('shows what came in by method and what drivers hold', (
      tester,
    ) async {
      await _tallScreen(tester);
      await tester.pumpWidget(
        _app(
          requestedDays: [],
          collections: const [
            CashBookCollection(method: 'cash', paymentCount: 3, amount: 4200),
            CashBookCollection(method: 'upi', paymentCount: 1, amount: 800),
          ],
          held: CashInHand(
            totalCash: 800,
            drivers: [
              DriverCashInHand(
                driverId: 'd1',
                driverName: 'Ramesh Patil',
                routeCount: 1,
                stopCount: 4,
                cashAmount: 800,
                upiAmount: 0,
                oldestRouteDate: DateTime(2026, 10, 30),
              ),
            ],
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('Today'), findsOneWidget);
      expect(find.text('Collected today'), findsOneWidget);
      expect(find.text('4 payments'), findsOneWidget);
      expect(find.text('Cash'), findsOneWidget);
      expect(find.text('UPI'), findsOneWidget);
      expect(find.text('3 payments'), findsOneWidget);
      expect(find.text('Ramesh Patil'), findsOneWidget);
      expect(find.text('4 stops · since 30 Oct'), findsOneWidget);
    });

    testWidgets('says so when nothing was collected and no one holds cash', (
      tester,
    ) async {
      await _tallScreen(tester);
      await tester.pumpWidget(_app(requestedDays: []));
      await tester.pumpAndSettle();

      expect(find.text('No payments recorded'), findsOneWidget);
      expect(
        find.text('No payments were recorded on this day.'),
        findsOneWidget,
      );
      expect(find.text('No driver is carrying cash.'), findsOneWidget);
    });

    testWidgets('steps back a day, and cannot go past today', (tester) async {
      await _tallScreen(tester);
      final days = <String>[];
      await tester.pumpWidget(_app(requestedDays: days));
      await tester.pumpAndSettle();

      final today = cashBookDay(DateTime.now());
      expect(days, [today]);

      final next = find.widgetWithIcon(IconButton, LpgIcons.chevronRight);
      expect(tester.widget<IconButton>(next).onPressed, isNull);

      await tester.tap(find.widgetWithIcon(IconButton, LpgIcons.back));
      await tester.pumpAndSettle();

      final yesterday = DateTime.now().subtract(const Duration(days: 1));
      expect(days.last, cashBookDay(yesterday));
      expect(find.text('Today'), findsNothing);
      expect(find.text('Collected on this day'), findsOneWidget);
      expect(tester.widget<IconButton>(next).onPressed, isNotNull);

      await tester.tap(next);
      await tester.pumpAndSettle();
      expect(find.text('Today'), findsOneWidget);
    });
  });
}
