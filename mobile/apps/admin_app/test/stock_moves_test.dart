import 'package:admin_app/src/features/fleet/data/fleet_providers.dart';
import 'package:admin_app/src/features/orders/data/orders_provider.dart';
import 'package:admin_app/src/features/stock/data/stock_provider.dart';
import 'package:admin_app/src/features/stock/presentation/stock_move_sheets.dart';
import 'package:admin_app/src/features/stock/presentation/stock_screen.dart';
import 'package:admin_app/src/providers.dart';
import 'package:api_client/api_client.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

const _godown = FleetWarehouse(
  id: 'w1',
  branchId: 'b1',
  name: 'Kothrud Godown',
  isActive: true,
);

const _domestic = CylinderTypeResponse(
  id: 'c1',
  name: 'Domestic 14.2 kg',
  weightKg: 14.2,
  isActive: true,
);

StockBalanceLine _line(String type, String status, int qty) =>
    StockBalanceLine(cylinderTypeId: type, status: status, quantity: qty);

final _lines = [
  _line('c1', 'filled', 42),
  _line('c1', 'empty', 40),
  _line('c1', 'damaged', 2),
];

const _rules = StatusTransitions(
  statusChange: {
    'filled': ['leakage', 'damaged'],
    'damaged': ['scrap'],
  },
  adjustment: {
    'empty': ['filled'],
  },
);

Future<void> _tall(WidgetTester tester) async {
  tester.view.physicalSize = const Size(800, 3600);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.reset);
}

Widget _host(Widget sheet, {List<ScaleSummary> scales = const []}) =>
    ProviderScope(
      overrides: [
        // Validation must stop before any request.
        fleetApiProvider.overrideWith(
          (ref) => throw StateError('the API must not be called'),
        ),
        weighmentApiProvider.overrideWith(
          (ref) => throw StateError('the API must not be called'),
        ),
        cylinderCatalogProvider.overrideWith((ref) async => [_domestic]),
        statusTransitionsProvider.overrideWith((ref) async => _rules),
        receiptScalesProvider.overrideWith((ref, id) async => scales),
      ],
      child: MaterialApp(
        theme: LpgTheme.light,
        home: Scaffold(body: sheet),
      ),
    );

void main() {
  test('suggests a tenth of the batch, rounded up, and at least one', () {
    expect(suggestedSample(40), 4);
    expect(suggestedSample(45), 5);
    expect(suggestedSample(3), 1);
  });

  test('knows what is on hand and which types the godown holds', () {
    expect(onHand(_lines, 'c1', 'filled'), 42);
    expect(onHand(_lines, 'c1', 'scrap'), 0);
    expect(onHand(_lines, null, 'filled'), 0);
    expect(heldTypes(_lines, [_domestic]), {'c1': 'Domestic 14.2 kg'});
    expect(heldTypes([_line('c1', 'filled', 0)], [_domestic]), isEmpty);
  });

  group('MoveStockSheet', () {
    testWidgets('only offers the moves the server allows', (tester) async {
      await _tall(tester);
      await tester.pumpWidget(
        _host(MoveStockSheet(godown: _godown, lines: _lines)),
      );
      await tester.pumpAndSettle();

      await tester.tap(find.text('Choose the status').first);
      await tester.pumpAndSettle();
      // Only statuses that have somewhere to go.
      expect(find.text('Filled'), findsOneWidget);
      expect(find.text('Damaged'), findsOneWidget);
      expect(find.text('Empty'), findsNothing);
      expect(find.text('Scrap'), findsNothing);
    });

    testWidgets('asks for what is missing, then for no more than is there', (
      tester,
    ) async {
      await _tall(tester);
      await tester.pumpWidget(
        _host(MoveStockSheet(godown: _godown, lines: _lines)),
      );
      await tester.pumpAndSettle();

      await tester.tap(find.text('Move stock'));
      await tester.pump();
      expect(find.text('Choose the cylinder.'), findsOneWidget);

      await tester.tap(find.text('Choose the cylinder'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Domestic 14.2 kg').last);
      await tester.pumpAndSettle();
      await tester.tap(find.text('Choose the status').first);
      await tester.pumpAndSettle();
      await tester.tap(find.text('Filled').last);
      await tester.pumpAndSettle();
      await tester.tap(find.text('Choose the status').first);
      await tester.pumpAndSettle();
      await tester.tap(find.text('Leaking').last);
      await tester.pumpAndSettle();

      expect(find.text('The system shows 42 filled.'), findsOneWidget);
      await tester.enterText(find.byType(TextFormField), '50');
      await tester.tap(find.text('Move stock'));
      await tester.pump();
      expect(find.text('Only 42 are recorded as filled.'), findsOneWidget);
    });

    testWidgets('a correction needs a reason on record', (tester) async {
      await _tall(tester);
      await tester.pumpWidget(
        _host(MoveStockSheet(godown: _godown, lines: _lines, correction: true)),
      );
      await tester.pumpAndSettle();

      expect(find.text('Save correction'), findsOneWidget);
      expect(find.text('Why'), findsOneWidget);
    });
  });

  group('ReturnToOmcSheet', () {
    testWidgets('needs the cylinder, the plant and a quantity that is there', (
      tester,
    ) async {
      await _tall(tester);
      await tester.pumpWidget(
        _host(ReturnToOmcSheet(godown: _godown, lines: _lines)),
      );
      await tester.pumpAndSettle();

      await tester.tap(find.text('Send back'));
      await tester.pump();
      expect(find.text('Choose the cylinder.'), findsOneWidget);
    });
  });

  group('ReceiptSampleSheet', () {
    final receipt = const GoodsReceipt(
      id: 'g1',
      cylinderTypeId: 'c1',
      quantity: 40,
      grnNumber: 'GRN-1',
    );

    testWidgets('says so when the godown has no scale, and can be skipped', (
      tester,
    ) async {
      await _tall(tester);
      await tester.pumpWidget(
        _host(ReceiptSampleSheet(godown: _godown, receipt: receipt)),
      );
      await tester.pumpAndSettle();

      expect(find.textContaining('No certified scale'), findsOneWidget);
      expect(find.text('Save sample'), findsNothing);
      expect(find.text('Skip'), findsOneWidget);
    });

    testWidgets('suggests a tenth of the batch and checks the numbers', (
      tester,
    ) async {
      await _tall(tester);
      await tester.pumpWidget(
        _host(
          ReceiptSampleSheet(godown: _godown, receipt: receipt),
          scales: const [
            ScaleSummary(
              id: 's1',
              warehouseId: 'w1',
              assetTag: 'SCALE-01',
              isExpired: false,
            ),
          ],
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('SCALE-01'), findsOneWidget);
      expect(find.text('4'), findsOneWidget);

      await tester.enterText(find.byType(TextFormField).first, '99');
      await tester.tap(find.text('Save sample'));
      await tester.pump();
      expect(
        find.text('Enter how many were weighed, up to 40.'),
        findsOneWidget,
      );
    });
  });

  testWidgets(
    'the stock screen lists the other actions and what each van carries',
    (tester) async {
      await _tall(tester);
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            stockGodownsProvider.overrideWith((ref) async => [_godown]),
            godownBalanceProvider.overrideWith((ref, id) async => _lines),
            reorderSignalsProvider.overrideWith((ref) async => const []),
            godownMovementsProvider.overrideWith((ref, id) async => const []),
            pendingCountsProvider.overrideWith((ref, id) async => const []),
            cylinderCatalogProvider.overrideWith((ref) async => [_domestic]),
            cylinderNamesProvider.overrideWith(
              (ref) async => {'c1': _domestic.name},
            ),
            fleetVehiclesProvider.overrideWith(
              (ref) async => const [
                FleetVehicle(
                  id: 'v1',
                  branchId: 'b1',
                  registrationNumber: 'MH12AB1234',
                  capacityUnits: 40,
                  status: 'active',
                ),
                FleetVehicle(
                  id: 'v2',
                  branchId: 'other',
                  registrationNumber: 'MH14ZZ0001',
                  capacityUnits: 40,
                  status: 'active',
                ),
              ],
            ),
            vanStockProvider.overrideWith(
              (ref, id) async => [
                _line('c1', 'filled', 12),
                _line('c1', 'empty', 3),
              ],
            ),
          ],
          child: MaterialApp(theme: LpgTheme.light, home: const StockScreen()),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('Change status'), findsOneWidget);
      expect(find.text('Correct stock'), findsOneWidget);
      expect(find.text('Return to OMC'), findsOneWidget);
      expect(find.text('On the vans'), findsOneWidget);
      expect(find.text('MH12AB1234'), findsOneWidget);
      // A van from another branch is not this godown's business.
      expect(find.text('MH14ZZ0001'), findsNothing);
      expect(find.textContaining('Domestic 14.2 kg 12'), findsOneWidget);
    },
  );
}
