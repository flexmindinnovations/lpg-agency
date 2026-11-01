import 'package:admin_app/src/features/orders/data/orders_provider.dart';
import 'package:admin_app/src/features/orders/presentation/order_list_screen.dart';
import 'package:api_client/api_client.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

Future<void> _pump(WidgetTester tester, Size size) async {
  tester.view.physicalSize = size;
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.reset);
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        adminOrdersProvider.overrideWith(
          (ref, args) async => const OrderPageResponse(items: [], total: 0),
        ),
      ],
      child: MaterialApp(theme: LpgTheme.light, home: const OrderListScreen()),
    ),
  );
  await tester.pump();
  await tester.pump();
}

void main() {
  testWidgets('tablet shows the list beside a detail pane', (tester) async {
    await _pump(tester, const Size(1280, 800));
    expect(find.text('Select an order to see its details.'), findsOneWidget);
  });

  testWidgets('phone keeps the single list', (tester) async {
    await _pump(tester, const Size(400, 800));
    expect(find.text('Select an order to see its details.'), findsNothing);
  });
}
