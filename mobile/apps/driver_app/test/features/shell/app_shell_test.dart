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
    notificationsRealtimeProvider.overrideWith((ref) => const Stream.empty()),
  ],
  child: MaterialApp.router(theme: LpgTheme.light, routerConfig: _router()),
);

/// Phone-sized window: the shell shows the bottom bar below 600px wide.
void _usePhoneSize(WidgetTester tester) {
  tester.view.physicalSize = const Size(390, 844);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.reset);
}

void main() {
  group('AppShell', () {
    testWidgets('renders the four tabs and starts on Today', (tester) async {
      _usePhoneSize(tester);
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

    testWidgets('uses a navigation rail on a tablet (DR-12)', (tester) async {
      tester.view.physicalSize = const Size(820, 1180);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.reset);
      await tester.pumpWidget(_app(unread: 3));
      await tester.pumpAndSettle();

      expect(find.byType(NavigationRail), findsOneWidget);
      expect(find.byType(NavigationBar), findsNothing);
      expect(find.text('TODAY BODY'), findsOneWidget);
      expect(find.text('3'), findsOneWidget);
    });
  });
}
