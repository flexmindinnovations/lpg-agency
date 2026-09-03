import 'package:design_system/design_system.dart';
import 'package:driver_app/src/offline/connectivity.dart';
import 'package:driver_app/src/offline/offline_banner.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

Widget _host({required bool online}) => ProviderScope(
  overrides: [connectivityProvider.overrideWith((ref) => Stream.value(online))],
  child: MaterialApp(
    theme: LpgTheme.light,
    home: const Scaffold(body: OfflineBanner()),
  ),
);

void main() {
  testWidgets('shows the offline strip when connectivity is lost', (
    tester,
  ) async {
    await tester.pumpWidget(_host(online: false));
    await tester.pumpAndSettle();

    expect(find.text('Offline — showing last synced data'), findsOneWidget);
  });

  testWidgets('renders nothing while online', (tester) async {
    await tester.pumpWidget(_host(online: true));
    await tester.pumpAndSettle();

    expect(find.textContaining('Offline'), findsNothing);
  });
}
