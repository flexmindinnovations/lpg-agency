import 'package:design_system/design_system.dart';
import 'package:driver_app/src/features/notifications/data/notifications_provider.dart';
import 'package:driver_app/src/features/shell/presentation/app_shell.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';

GoRouter _router() => GoRouter(
  initialLocation: '/',
  routes: [
    StatefulShellRoute.indexedStack(
      builder: (context, state, shell) => AppShell(navigationShell: shell),
      branches: [
        for (final (path, body) in const [
          ('/', 'TODAY BODY'),
          ('/deliveries', 'DELIVERIES BODY'),
          ('/alerts', 'ALERTS BODY'),
          ('/profile', 'PROFILE BODY'),
        ])
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: path,
                builder: (_, _) => Scaffold(body: Center(child: Text(body))),
              ),
            ],
          ),
      ],
    ),
  ],
);

Widget _app({int unread = 0}) => ProviderScope(
  overrides: [
    unreadNotificationCountProvider.overrideWith((ref) async => unread),
    pushMessagesProvider.overrideWith((ref) => const Stream.empty()),
  ],
  child: MaterialApp.router(theme: LpgTheme.light, routerConfig: _router()),
);

void main() {
  group('AppShell', () {
    testWidgets('renders the four tabs and starts on Today', (tester) async {
      await tester.pumpWidget(_app());
      await tester.pumpAndSettle();

      expect(find.byType(NavigationBar), findsOneWidget);
      expect(find.text('TODAY BODY'), findsOneWidget);
      for (final label in ['Today', 'Deliveries', 'Alerts', 'Profile']) {
        expect(
          find.widgetWithText(NavigationDestination, label),
          findsOneWidget,
        );
      }
    });

    testWidgets('tapping a tab switches the visible branch', (tester) async {
      await tester.pumpWidget(_app());
      await tester.pumpAndSettle();

      await tester.tap(find.text('Deliveries'));
      await tester.pumpAndSettle();
      expect(find.text('DELIVERIES BODY'), findsOneWidget);

      await tester.tap(find.text('Alerts'));
      await tester.pumpAndSettle();
      expect(find.text('ALERTS BODY'), findsOneWidget);

      await tester.tap(find.text('Profile'));
      await tester.pumpAndSettle();
      expect(find.text('PROFILE BODY'), findsOneWidget);
    });

    testWidgets('the Alerts tab shows a badge when there are unread alerts', (
      tester,
    ) async {
      await tester.pumpWidget(_app(unread: 3));
      await tester.pumpAndSettle();

      expect(find.widgetWithText(Badge, '3'), findsOneWidget);
    });
  });
}
