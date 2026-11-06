// Story 0.4 for the Driver app: Today keeps its skeleton until the first
// answer, retries a transient failure once without showing an error, shows the
// error only if the retry also fails, and keeps the route on screen when a
// refresh fails.
import 'package:api_client/api_client.dart';
import 'package:core/core.dart';
import 'package:design_system/design_system.dart';
import 'package:driver_app/src/features/cash_handover/data/cash_handover_provider.dart';
import 'package:driver_app/src/features/delivery/data/active_route_provider.dart';
import 'package:driver_app/src/features/delivery/presentation/today_screen.dart';
import 'package:driver_app/src/features/van_load/data/van_load_provider.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

const _offline = FailureException(
  Failure(
    message: 'Cannot reach the server.',
    errorCode: 'NETWORK_UNAVAILABLE',
  ),
);

const _after = Duration(milliseconds: 100);

/// The active-route body: plays [steps] in order (the last repeats). `null`
/// is "no route assigned"; an exception is thrown.
Future<RouteSummary?> Function(Ref) _script(
  List<Object?> steps, {
  List<int>? calls,
}) {
  var n = 0;
  return (ref) async {
    final step = steps[n.clamp(0, steps.length - 1)];
    n++;
    calls?.add(n);
    if (step is Exception) throw step;
    return step as RouteSummary?;
  };
}

Future<void> _pump(
  WidgetTester tester,
  Future<RouteSummary?> Function(Ref) body,
) {
  tester.view.physicalSize = const Size(1200, 4000);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.reset);
  return tester.pumpWidget(
    ProviderScope(
      retry: quietRetry,
      overrides: [
        activeRouteProvider.overrideWith(body),
        pendingCashHandoversProvider.overrideWith((ref) async => []),
        pendingLoadProvider.overrideWith((ref) async => null),
        myCashInHandProvider.overrideWith((ref) async => null),
        routeHistoryProvider.overrideWith((ref) async => []),
      ],
      child: MaterialApp(theme: LpgTheme.light, home: const TodayScreen()),
    ),
  );
}

Future<void> _pastRetryDelay(WidgetTester tester) async {
  await tester.pump(quietRetryDelay + _after);
  await tester.pump(const Duration(seconds: 1));
}

void main() {
  testWidgets('first request fails, retry succeeds: skeleton, never the '
      'error, then the screen', (tester) async {
    await _pump(tester, _script([_offline, null]));

    await tester.pump(_after);
    expect(find.byType(LpgSkeletonGroup), findsOneWidget);
    expect(find.byType(LpgErrorState), findsNothing);

    await tester.pump(quietRetryDelay - const Duration(milliseconds: 300));
    expect(find.byType(LpgErrorState), findsNothing);
    expect(find.byType(LpgSkeletonGroup), findsOneWidget);

    await _pastRetryDelay(tester);
    expect(find.byType(LpgErrorState), findsNothing);
    expect(find.text('Nothing on the road yet'), findsOneWidget);
  });

  testWidgets('shows the error only when the retry fails as well, and Retry '
      'recovers', (tester) async {
    final calls = <int>[];
    await _pump(tester, _script([_offline, _offline, null], calls: calls));

    await tester.pump(_after);
    expect(find.byType(LpgErrorState), findsNothing);

    await _pastRetryDelay(tester);
    expect(find.byType(LpgErrorState), findsOneWidget);
    expect(calls.length, 2);

    await tester.tap(find.text('Retry'));
    await tester.pump(_after);
    await tester.pump(const Duration(seconds: 1));
    expect(find.byType(LpgErrorState), findsNothing);
    expect(find.text('Nothing on the road yet'), findsOneWidget);
  });

  testWidgets('does not retry a refusal that will not change', (tester) async {
    final calls = <int>[];
    await _pump(
      tester,
      _script([
        const FailureException(Failure(message: 'No.', errorCode: 'FORBIDDEN')),
      ], calls: calls),
    );

    await tester.pump(_after);
    expect(find.byType(LpgErrorState), findsOneWidget);
    await tester.pump(quietRetryDelay * 2);
    expect(calls, [1]);
  });

  testWidgets('a failed refresh keeps the screen that is already shown', (
    tester,
  ) async {
    await _pump(tester, _script([null, _offline]));
    await tester.pump(_after);
    await tester.pump(const Duration(seconds: 1));
    expect(find.text('Nothing on the road yet'), findsOneWidget);

    ProviderScope.containerOf(
      tester.element(find.byType(TodayScreen)),
    ).invalidate(activeRouteProvider);
    await tester.pump(_after);
    expect(find.text('Nothing on the road yet'), findsOneWidget);

    await _pastRetryDelay(tester);
    expect(find.text('Nothing on the road yet'), findsOneWidget);
    expect(find.byType(LpgErrorState), findsNothing);
  });
}
