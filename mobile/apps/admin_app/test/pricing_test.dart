import 'dart:convert';
import 'dart:typed_data';

import 'package:admin_app/src/features/fleet/data/fleet_providers.dart';
import 'package:admin_app/src/features/orders/data/orders_provider.dart';
import 'package:admin_app/src/features/pricing/data/pricing_provider.dart';
import 'package:admin_app/src/features/pricing/presentation/pricing_presentation.dart';
import 'package:admin_app/src/features/pricing/presentation/pricing_screen.dart';
import 'package:admin_app/src/features/pricing/presentation/set_price_sheet.dart';
import 'package:admin_app/src/providers.dart';
import 'package:api_client/api_client.dart';
import 'package:design_system/design_system.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

final _now = DateTime.utc(2026, 10, 30, 12);

PriceEntry _entry(
  String id,
  double price,
  DateTime from, {
  String cylinder = 'c1',
  String customer = 'domestic',
  String? branch,
}) => PriceEntry(
  id: id,
  cylinderTypeId: cylinder,
  customerType: customer,
  branchId: branch,
  price: price,
  effectiveFrom: from,
);

const _domestic = CylinderTypeResponse(
  id: 'c1',
  name: 'Domestic 14.2kg',
  weightKg: 14.2,
  isActive: true,
);
const _commercial = CylinderTypeResponse(
  id: 'c2',
  name: 'Commercial 19kg',
  weightKg: 19,
  isActive: true,
);

/// A Dio that counts requests and answers each with an empty price entry.
class _CountingAdapter implements HttpClientAdapter {
  int requests = 0;

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    requests++;
    return ResponseBody.fromString(
      jsonEncode({
        'id': 'p',
        'cylinder_type_id': 'c1',
        'customer_type': 'domestic',
        'price': '1',
        'effective_from': '2026-10-30T00:00:00Z',
      }),
      201,
      headers: {
        Headers.contentTypeHeader: [Headers.jsonContentType],
      },
    );
  }

  @override
  void close({bool force = false}) {}
}

void main() {
  group('price rows', () {
    final rows = buildPriceRows(
      [
        _entry('a', 900, DateTime.utc(2026, 1, 1)),
        _entry('b', 905.5, DateTime.utc(2026, 9, 1)),
        _entry('c', 920, DateTime.utc(2026, 11, 15)),
        _entry('d', 1500, DateTime.utc(2026, 1, 1), customer: 'commercial'),
        _entry('e', 880, DateTime.utc(2026, 1, 1), branch: 'br1'),
        _entry('f', 2100, DateTime.utc(2026, 1, 1), cylinder: 'c2'),
      ],
      ['c1', 'c2'],
    );

    test('one row per cylinder, customer type and branch, in order', () {
      expect(
        rows.map((r) => '${r.cylinderTypeId}/${r.customerType}/${r.branchId}'),
        [
          'c1/domestic/null',
          'c1/domestic/br1',
          'c1/commercial/null',
          'c2/domestic/null',
        ],
      );
    });

    test('the price in force is the latest that has started', () {
      final row = rows.first;
      expect(row.current(_now)!.price, 905.5);
      expect(row.upcoming(_now).map((e) => e.price), [920]);
      expect(row.earlier(_now).map((e) => e.price), [900]);
    });

    test('before anything has started there is no current price', () {
      final row = rows.first;
      final early = DateTime.utc(2025, 1, 1);
      expect(row.current(early), isNull);
      expect(row.earlier(early), isEmpty);
      expect(row.upcoming(early), hasLength(3));
    });

    test('a price saved a moment ago is not mistaken for a scheduled one', () {
      final justNow = buildPriceRows(
        [
          _entry('a', 900, DateTime.utc(2026, 1, 1)),
          // Stamped by a server clock a few seconds ahead of this phone.
          _entry('b', 910, _now.add(const Duration(seconds: 5))),
        ],
        ['c1'],
      ).single;

      expect(justNow.current(_now)!.price, 910);
      expect(justNow.upcoming(_now), isEmpty);
      expect(justNow.earlier(_now).map((e) => e.price), [900]);
    });

    test('flags a big jump but not an ordinary revision', () {
      expect(isLargeChange(905.5, 9055), isTrue);
      expect(isLargeChange(905.5, 600), isTrue);
      expect(isLargeChange(905.5, 930), isFalse);
      expect(isLargeChange(0, 500), isFalse);
      expect(changeLabel(905.5, 1000), '+10%');
      expect(changeLabel(1000, 920), '-8%');
    });
  });

  group('PricingScreen', () {
    Widget app({List<PriceProposal> proposals = const []}) {
      final past = DateTime.now().subtract(const Duration(days: 60));
      final future = DateTime.now().add(const Duration(days: 10));
      return ProviderScope(
        overrides: [
          priceEntriesProvider.overrideWith(
            (ref) async => [
              _entry('a', 900, past),
              _entry('b', 920, future),
              _entry('c', 1500, past, customer: 'commercial'),
              _entry('d', 2100, past, cylinder: 'c2'),
              _entry('e', 880, past, branch: 'br1'),
            ],
          ),
          priceProposalsProvider.overrideWith((ref) async => proposals),
          cylinderCatalogProvider.overrideWith(
            (ref) async => [_domestic, _commercial],
          ),
          fleetBranchesProvider.overrideWith(
            (ref) async => const [
              FleetBranch(id: 'br1', name: 'Hadapsar', isActive: true),
            ],
          ),
        ],
        child: MaterialApp(theme: LpgTheme.light, home: const PricingScreen()),
      );
    }

    Future<void> tall(WidgetTester tester) async {
      tester.view.physicalSize = const Size(800, 3200);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.reset);
    }

    testWidgets('lists each cylinder with its prices and what is coming', (
      tester,
    ) async {
      await tall(tester);
      await tester.pumpWidget(app());
      await tester.pumpAndSettle();

      expect(find.text('Domestic 14.2kg'), findsOneWidget);
      expect(find.text('Commercial 19kg'), findsOneWidget);
      expect(find.text('₹900.00'), findsOneWidget);
      expect(find.textContaining('Changes to ₹920.00 on'), findsOneWidget);
      expect(find.text('Domestic · Hadapsar'), findsOneWidget);
      expect(find.text('₹880.00'), findsOneWidget);
      expect(find.text('₹1,500.00'), findsOneWidget);
      expect(find.textContaining('Rate changes to review'), findsNothing);
    });

    testWidgets('puts rate changes to review at the top', (tester) async {
      await tall(tester);
      await tester.pumpWidget(
        app(
          proposals: [
            PriceProposal(
              id: 'r1',
              cylinderTypeId: 'c1',
              customerType: 'domestic',
              proposedPrice: 915,
              effectiveFrom: DateTime(2026, 11, 1),
              sourceUrl: 'https://omc.test/rates',
            ),
          ],
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('Rate changes to review (1)'), findsOneWidget);
      expect(find.text('₹915.00'), findsOneWidget);
    });
  });

  group('SetPriceSheet', () {
    Widget host(PriceRow? row, _CountingAdapter adapter) {
      final dio = Dio()..httpClientAdapter = adapter;
      return ProviderScope(
        overrides: [
          priceListApiProvider.overrideWithValue(PriceListApi(dio)),
          cylinderCatalogProvider.overrideWith((ref) async => [_domestic]),
          fleetBranchesProvider.overrideWith((ref) async => const []),
        ],
        child: MaterialApp(
          theme: LpgTheme.light,
          home: Scaffold(body: SetPriceSheet(row: row)),
        ),
      );
    }

    final row = buildPriceRows(
      [_entry('a', 905.5, DateTime.utc(2026, 1, 1))],
      ['c1'],
    ).single;

    Future<void> tall(WidgetTester tester) async {
      tester.view.physicalSize = const Size(800, 3200);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.reset);
    }

    testWidgets('a new price needs a cylinder and an amount', (tester) async {
      await tall(tester);
      final adapter = _CountingAdapter();
      await tester.pumpWidget(host(null, adapter));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Save price'));
      await tester.pump();
      expect(find.text('Choose the cylinder.'), findsOneWidget);
      expect(adapter.requests, 0);
    });

    testWidgets('saving the price it already has is refused', (tester) async {
      await tall(tester);
      final adapter = _CountingAdapter();
      await tester.pumpWidget(host(row, adapter));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Save price'));
      await tester.pump();
      expect(find.text('That is already the price.'), findsOneWidget);
      expect(adapter.requests, 0);
    });

    testWidgets('a slipped decimal point asks first and can be cancelled', (
      tester,
    ) async {
      await tall(tester);
      final adapter = _CountingAdapter();
      await tester.pumpWidget(host(row, adapter));
      await tester.pumpAndSettle();

      await tester.enterText(find.byType(TextFormField), '9055.00');
      await tester.tap(find.text('Save price'));
      await tester.pumpAndSettle();

      expect(find.textContaining('Change the price by +900%'), findsOneWidget);
      await tester.tap(find.text('Cancel'));
      await tester.pumpAndSettle();
      expect(adapter.requests, 0);
    });

    testWidgets('a normal revision saves without asking', (tester) async {
      await tall(tester);
      final adapter = _CountingAdapter();
      await tester.pumpWidget(host(row, adapter));
      await tester.pumpAndSettle();

      await tester.enterText(find.byType(TextFormField), '930.00');
      await tester.tap(find.text('Save price'));
      await tester.pumpAndSettle();

      expect(find.textContaining('Change the price by'), findsNothing);
      expect(adapter.requests, 1);
    });
  });
}
