import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:driver_app/main.dart';

void main() {
  testWidgets('app shell renders', (tester) async {
    await tester.pumpWidget(const ProviderScope(child: DriverApp()));
    await tester.pumpAndSettle();

    expect(find.text('LPG Agency'), findsWidgets);
    expect(find.text('Repository foundation'), findsOneWidget);
  });

  testWidgets('shell has a Material scaffold', (tester) async {
    await tester.pumpWidget(const ProviderScope(child: DriverApp()));
    await tester.pumpAndSettle();

    expect(find.byType(Scaffold), findsOneWidget);
  });
}
