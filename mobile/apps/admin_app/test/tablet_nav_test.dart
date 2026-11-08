import 'package:admin_app/src/features/approvals/data/approvals_provider.dart';
import 'package:admin_app/src/features/shell/presentation/tablet_nav.dart';
import 'package:admin_app/src/i18n/admin_strings.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';

Future<void> _pump(WidgetTester tester, Size size) async {
  tester.view.physicalSize = size;
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.reset);
  final router = GoRouter(
    initialLocation: '/customers',
    routes: [
      GoRoute(
        path: '/customers',
        builder: (_, _) => const AdminTabletFrame(child: Text('Body')),
      ),
      GoRoute(path: '/orders', builder: (_, _) => const Text('Orders page')),
    ],
  );
  await tester.pumpWidget(
    ProviderScope(
      overrides: [pendingCashHandoversProvider.overrideWith((ref) async => [])],
      child: MaterialApp.router(
        theme: LpgTheme.light,
        localizationsDelegates: adminLocalizationsDelegates,
        routerConfig: router,
      ),
    ),
  );
  await tester.pumpAndSettle();
}

void main() {
  test('screens map to their rail entry, others to More', () {
    expect(tabletIndexFor('/'), 0);
    expect(tabletIndexFor('/orders/new'), 1);
    expect(tabletIndexFor('/order-view/abc'), 1);
    expect(tabletIndexFor('/fleet/van-new'), 2);
    expect(tabletIndexFor('/customers/42'), 3);
    expect(tabletIndexFor('/approvals'), 6);
    expect(tabletIndexFor('/stock'), 7);
    expect(tabletIndexFor('/pricing'), 7);
  });

  testWidgets('a tablet gets the rail with every entry beside the screen', (
    tester,
  ) async {
    await _pump(tester, const Size(1280, 800));
    expect(find.byType(NavigationRail), findsOneWidget);
    expect(find.text('Body'), findsOneWidget);
    for (final label in [
      'Dashboard',
      'Orders',
      'Dispatch',
      'Customers',
      'Invoices',
      'Complaints',
      'Approvals',
      'More',
    ]) {
      expect(find.text(label), findsOneWidget, reason: label);
    }
    await tester.tap(find.text('Orders'));
    await tester.pumpAndSettle();
    expect(find.text('Orders page'), findsOneWidget);
  });

  testWidgets('the rail scrolls on a short tablet instead of overflowing', (
    tester,
  ) async {
    await _pump(tester, const Size(1024, 480));
    expect(tester.takeException(), isNull);
  });

  testWidgets('a phone gets the screen alone', (tester) async {
    await _pump(tester, const Size(400, 800));
    expect(find.byType(NavigationRail), findsNothing);
    expect(find.text('Body'), findsOneWidget);
  });
}
