import 'package:admin_app/src/features/orders/data/orders_provider.dart';
import 'package:admin_app/src/features/stock/data/stock_provider.dart';
import 'package:admin_app/src/features/stock/presentation/count_review_sheet.dart';
import 'package:admin_app/src/features/stock/presentation/receive_stock_sheet.dart';
import 'package:admin_app/src/features/stock/presentation/stock_presentation.dart';
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
const _commercial = CylinderTypeResponse(
  id: 'c2',
  name: 'Commercial 19 kg',
  weightKg: 19,
  isActive: true,
);

StockBalanceLine _line(String type, String status, int qty) =>
    StockBalanceLine(cylinderTypeId: type, status: status, quantity: qty);

InventoryTransaction _move(
  String type, {
  String? from,
  String to = 'filled',
  int qty = 10,
}) => InventoryTransaction(
  id: 'm-$type',
  cylinderTypeId: 'c1',
  type: type,
  fromStatus: from,
  toStatus: to,
  quantity: qty,
  performedAt: DateTime.now().subtract(const Duration(hours: 2)),
);

ReconciliationRecord _count({int expected = 42, int actual = 40}) =>
    ReconciliationRecord(
      id: 'r1',
      cylinderTypeId: 'c1',
      status: 'filled',
      expectedQuantity: expected,
      actualQuantity: actual,
      variance: actual - expected,
      state: 'pending',
      recordedAt: DateTime.now().subtract(const Duration(minutes: 5)),
    );

void main() {
  group('stock wording and numbers', () {
    test('folds balance lines per cylinder type in catalogue order', () {
      final types = groupByCylinderType(
        [
          _line('c2', 'filled', 8),
          _line('c1', 'filled', 30),
          _line('c1', 'filled', 12),
          _line('c1', 'empty', 40),
          _line('c1', 'scrap', 0),
          _line('gone', 'filled', 0),
        ],
        ['c1', 'c2'],
      );

      expect(types.map((t) => t.cylinderTypeId), ['c1', 'c2']);
      expect(types.first.filled, 42);
      expect(types.first.others.map((o) => '${o.key} ${o.value}'), [
        'empty 40',
      ]);
    });

    test('says what happened at a godown, not on the van', () {
      expect(movementLabel('unload'), 'Sent out on a van');
      expect(movementLabel('load'), 'Came back from a van');
      expect(movementLabel('grn_receipt'), 'Received from OMC');
      expect(movementLabel('something_new'), 'Something new');
    });

    test('signs a movement by what it did to the godown', () {
      expect(signedQuantity(_move('grn_receipt', qty: 40)), '+40');
      expect(signedQuantity(_move('unload', qty: 6)), '-6');
      expect(signedQuantity(_move('reconciliation', qty: 2)), '+2');
      expect(
        signedQuantity(_move('reconciliation', from: 'filled', qty: 2)),
        '-2',
      );
      expect(
        signedQuantity(
          _move('status_change', from: 'filled', to: 'leakage', qty: 1),
        ),
        '1',
      );
    });

    test('names a status move from and to', () {
      expect(movementStatus(_move('grn_receipt')), 'Filled');
      expect(
        movementStatus(_move('adjustment', from: 'filled', to: 'leakage')),
        'Filled to Leaking',
      );
    });

    test('explains what approving a count does', () {
      expect(countOutcome(_count(actual: 40)), contains('down by 2 cylinders'));
      expect(countOutcome(_count(actual: 43)), contains('adds 1 cylinder'));
      expect(countOutcome(_count(actual: 42)), contains('stays as it is'));
    });
  });

  group('StockScreen', () {
    Widget app({
      List<ReorderSignal> signals = const [],
      List<ReconciliationRecord> pending = const [],
    }) => ProviderScope(
      overrides: [
        stockGodownsProvider.overrideWith((ref) async => [_godown]),
        godownBalanceProvider.overrideWith(
          (ref, id) async => [
            _line('c1', 'filled', 42),
            _line('c1', 'empty', 40),
            _line('c1', 'damaged', 2),
            _line('c2', 'filled', 4),
          ],
        ),
        reorderSignalsProvider.overrideWith((ref) async => signals),
        godownMovementsProvider.overrideWith(
          (ref, id) async => [_move('grn_receipt', qty: 40)],
        ),
        pendingCountsProvider.overrideWith((ref, id) async => pending),
        cylinderCatalogProvider.overrideWith(
          (ref) async => [_domestic, _commercial],
        ),
        cylinderNamesProvider.overrideWith(
          (ref) async => {'c1': _domestic.name, 'c2': _commercial.name},
        ),
      ],
      child: MaterialApp(theme: LpgTheme.light, home: const StockScreen()),
    );

    Future<void> tall(WidgetTester tester) async {
      tester.view.physicalSize = const Size(800, 3600);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.reset);
    }

    testWidgets('shows filled stock, the rest of the floor and movements', (
      tester,
    ) async {
      await tall(tester);
      await tester.pumpWidget(app());
      await tester.pumpAndSettle();

      expect(find.text('46'), findsOneWidget); // 42 + 4 filled
      expect(find.text('Kothrud Godown'), findsOneWidget);
      expect(find.text('Domestic 14.2 kg'), findsOneWidget);
      expect(find.text('Empty 40 · Damaged 2'), findsOneWidget);
      expect(find.text('Received from OMC'), findsOneWidget);
      expect(find.text('+40'), findsOneWidget);
      expect(find.text('No counts are waiting.'), findsOneWidget);
      expect(find.byType(LpgBanner), findsNothing);
    });

    testWidgets('warns about a cylinder running low', (tester) async {
      await tall(tester);
      await tester.pumpWidget(
        app(
          signals: const [
            ReorderSignal(
              warehouseId: 'w1',
              cylinderTypeId: 'c2',
              onHand: 4,
              reorderPoint: 20,
              safetyStock: 5,
            ),
            // Another godown's shortage is not this one's problem.
            ReorderSignal(
              warehouseId: 'other',
              cylinderTypeId: 'c1',
              onHand: 0,
              reorderPoint: 10,
              safetyStock: 2,
            ),
          ],
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('Commercial 19 kg is running low'), findsOneWidget);
      expect(
        find.textContaining('4 filled left, reorder at 20'),
        findsOneWidget,
      );
      expect(find.byType(LpgBanner), findsOneWidget);
    });

    testWidgets('lists a count waiting with its difference', (tester) async {
      await tall(tester);
      await tester.pumpWidget(app(pending: [_count()]));
      await tester.pumpAndSettle();

      expect(find.text('Domestic 14.2 kg · Filled'), findsOneWidget);
      expect(find.text('System 42, counted 40'), findsOneWidget);
      expect(find.text('-2'), findsOneWidget);
    });
  });

  group('sheets', () {
    Widget host(Widget sheet) => ProviderScope(
      overrides: [
        // Validation must stop before any request.
        fleetApiProvider.overrideWith(
          (ref) => throw StateError('the API must not be called'),
        ),
        cylinderCatalogProvider.overrideWith((ref) async => [_domestic]),
        cylinderNamesProvider.overrideWith(
          (ref) async => {'c1': _domestic.name},
        ),
      ],
      child: MaterialApp(
        theme: LpgTheme.light,
        home: Scaffold(body: sheet),
      ),
    );

    testWidgets('receiving needs a cylinder and a quantity', (tester) async {
      tester.view.physicalSize = const Size(800, 3600);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.reset);
      await tester.pumpWidget(host(const ReceiveStockSheet(godown: _godown)));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Add to stock'));
      await tester.pump();
      expect(find.text('Choose which cylinder arrived.'), findsOneWidget);

      await tester.tap(find.text('Choose the cylinder'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Domestic 14.2 kg'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Add to stock'));
      await tester.pump();
      expect(
        find.text('Enter how many cylinders came off the truck.'),
        findsOneWidget,
      );
    });

    testWidgets('rejecting a count asks why first', (tester) async {
      tester.view.physicalSize = const Size(800, 3600);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.reset);
      await tester.pumpWidget(host(CountReviewSheet(count: _count())));
      await tester.pumpAndSettle();

      expect(find.textContaining('down by 2 cylinders'), findsOneWidget);

      await tester.tap(find.text('Reject'));
      await tester.pump();
      await tester.tap(find.text('Reject count'));
      await tester.pump();

      expect(find.textContaining('Say why'), findsOneWidget);
    });
  });
}
