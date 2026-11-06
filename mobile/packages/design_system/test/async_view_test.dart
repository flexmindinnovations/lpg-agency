import 'package:core/core.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:riverpod/riverpod.dart';

const _offline = FailureException(
  Failure(message: 'raw server words', errorCode: 'NETWORK_UNAVAILABLE'),
);

AsyncValue<int> get _loading => const AsyncLoading<int>();

/// The state a provider holds after a refresh failed behind loaded data,
/// obtained by running one (the only supported way to build it).
Future<AsyncValue<int>> _staleError(Object error) async {
  var calls = 0;
  final provider = FutureProvider<int>((ref) async {
    if (calls++ == 0) return 7;
    throw error;
  });
  final container = ProviderContainer(retry: (_, _) => null);
  addTearDown(container.dispose);
  container.listen(provider, (_, _) {});
  await container.read(provider.future);
  container.invalidate(provider);
  await expectLater(container.read(provider.future), throwsA(anything));
  return container.read(provider);
}

/// A refresh in flight: the loaded value, loading again.
Future<AsyncValue<int>> _refreshing() async {
  final provider = FutureProvider<int>((ref) async => 7);
  final container = ProviderContainer();
  addTearDown(container.dispose);
  container.listen(provider, (_, _) {});
  await container.read(provider.future);
  container.invalidate(provider);
  return container.read(provider);
}

Widget _host(Widget child) => MaterialApp(
  theme: LpgTheme.light,
  home: Scaffold(body: child),
);

LpgAsyncView<int> _view(
  AsyncValue<int> value, {
  VoidCallback? onRetry,
  bool offline = false,
  bool Function(int)? isEmpty,
  bool showStaleNotice = true,
}) => LpgAsyncView<int>(
  value: value,
  onRetry: onRetry,
  offline: offline,
  isEmpty: isEmpty,
  showStaleNotice: showStaleNotice,
  skeleton: const Text('skeleton'),
  empty: const Text('nothing here'),
  data: (context, n) => Text('value $n'),
);

void main() {
  group('LpgAsyncView', () {
    testWidgets('shows the skeleton until the first answer', (tester) async {
      await tester.pumpWidget(_host(_view(_loading)));

      expect(find.text('skeleton'), findsOneWidget);
      expect(find.byType(LpgErrorState), findsNothing);
    });

    testWidgets('shows the data', (tester) async {
      await tester.pumpWidget(_host(_view(const AsyncData(7))));

      expect(find.text('value 7'), findsOneWidget);
      expect(find.byType(LpgBanner), findsNothing);
    });

    testWidgets('shows the empty state when there is nothing', (tester) async {
      await tester.pumpWidget(
        _host(_view(const AsyncData(0), isEmpty: (n) => n == 0)),
      );

      expect(find.text('nothing here'), findsOneWidget);
      expect(find.text('value 0'), findsNothing);
    });

    testWidgets('an error is friendly and never the server\'s words', (
      tester,
    ) async {
      var retries = 0;
      await tester.pumpWidget(
        _host(
          _view(
            AsyncError<int>(_offline, StackTrace.empty),
            onRetry: () => retries++,
          ),
        ),
      );

      expect(find.text('No internet'), findsOneWidget);
      expect(find.text('raw server words'), findsNothing);
      await tester.tap(find.text('Retry'));
      expect(retries, 1);
    });

    testWidgets('shows a support code only where it helps', (tester) async {
      await tester.pumpWidget(
        _host(
          _view(
            AsyncError<int>(
              const FailureException(
                Failure(message: 'x', errorCode: 'INTERNAL_SERVER_ERROR'),
              ),
              StackTrace.empty,
            ),
            onRetry: () {},
          ),
        ),
      );

      expect(find.text('Code: INTERNAL_SERVER_ERROR'), findsOneWidget);
      expect(find.textContaining('code shown below'), findsOneWidget);
    });

    testWidgets('no Retry where asking again cannot help', (tester) async {
      await tester.pumpWidget(
        _host(
          _view(
            AsyncError<int>(
              const FailureException(
                Failure(message: 'x', errorCode: 'PERMISSION_DENIED'),
              ),
              StackTrace.empty,
            ),
            onRetry: () {},
          ),
        ),
      );

      expect(
        find.text('This is not available for your account'),
        findsOneWidget,
      );
      expect(find.text('Retry'), findsNothing);
    });

    testWidgets('a refresh in progress keeps the data and adds nothing', (
      tester,
    ) async {
      final refreshing = (await tester.runAsync(_refreshing))!;
      expect(refreshing.isLoading, isTrue);
      await tester.pumpWidget(_host(_view(refreshing)));

      expect(find.text('value 7'), findsOneWidget);
      expect(find.byType(LpgBanner), findsNothing);
    });

    testWidgets('a failed refresh keeps the data and adds a notice with '
        'Retry', (tester) async {
      var retries = 0;
      await tester.pumpWidget(
        _host(
          _view(
            (await tester.runAsync(() => _staleError(_offline)))!,
            onRetry: () => retries++,
          ),
        ),
      );

      expect(find.text('value 7'), findsOneWidget);
      expect(find.text(LpgErrorCopy.staleNotice), findsOneWidget);
      expect(find.byType(LpgErrorState), findsNothing);
      await tester.tap(find.text('Retry'));
      expect(retries, 1);
    });

    testWidgets('the stale notice can be switched off', (tester) async {
      await tester.pumpWidget(
        _host(
          _view(
            (await tester.runAsync(() => _staleError(_offline)))!,
            showStaleNotice: false,
          ),
        ),
      );

      expect(find.text('value 7'), findsOneWidget);
      expect(find.byType(LpgBanner), findsNothing);
    });

    testWidgets('the offline notice shows above the data', (tester) async {
      await tester.pumpWidget(_host(_view(const AsyncData(7), offline: true)));

      expect(find.text(LpgErrorCopy.offlineNotice), findsOneWidget);
      expect(find.text('value 7'), findsOneWidget);
    });

    testWidgets('expand lets scrollable data sit under the notice', (
      tester,
    ) async {
      await tester.pumpWidget(
        _host(
          LpgAsyncView<int>(
            value: const AsyncData(3),
            offline: true,
            expand: true,
            data: (context, n) => ListView(
              children: [for (var i = 0; i < n; i++) Text('row $i')],
            ),
          ),
        ),
      );

      expect(tester.takeException(), isNull);
      expect(find.text('row 2'), findsOneWidget);
      expect(find.text(LpgErrorCopy.offlineNotice), findsOneWidget);
    });
  });

  group('SliverLpgAsyncView', () {
    Widget sliverHost(AsyncValue<int> value, {bool Function(int)? isEmpty}) =>
        _host(
          CustomScrollView(
            slivers: [
              SliverLpgAsyncView<int>(
                value: value,
                isEmpty: isEmpty,
                skeleton: const Text('skeleton'),
                empty: const Text('nothing here'),
                onRetry: () {},
                data: (context, n) => SliverList.list(
                  children: [for (var i = 0; i < n; i++) Text('row $i')],
                ),
              ),
            ],
          ),
        );

    testWidgets('skeleton, data, empty and error are all slivers', (
      tester,
    ) async {
      await tester.pumpWidget(sliverHost(_loading));
      expect(find.text('skeleton'), findsOneWidget);

      await tester.pumpWidget(sliverHost(const AsyncData(2)));
      expect(find.text('row 1'), findsOneWidget);

      await tester.pumpWidget(
        sliverHost(const AsyncData(0), isEmpty: (n) => n == 0),
      );
      expect(find.text('nothing here'), findsOneWidget);

      await tester.pumpWidget(
        sliverHost(AsyncError<int>(_offline, StackTrace.empty)),
      );
      expect(find.text('No internet'), findsOneWidget);
      expect(tester.takeException(), isNull);
    });

    testWidgets('a failed refresh keeps the rows and adds the notice', (
      tester,
    ) async {
      await tester.pumpWidget(
        sliverHost((await tester.runAsync(() => _staleError(_offline)))!),
      );

      expect(find.text('row 6'), findsOneWidget);
      expect(find.text(LpgErrorCopy.staleNotice), findsOneWidget);
    });
  });

  group('error copy', () {
    test('every kind has a title, a message and no server sentence', () {
      for (final kind in ErrorKind.values) {
        final copy = LpgErrorCopy.of(kind);
        expect(copy.title, isNotEmpty, reason: '$kind');
        expect(copy.message, isNotEmpty, reason: '$kind');
        expect(copy.message, isNot(contains('below')), reason: '$kind');
      }
    });

    test('only the server message points at the code, and only with one', () {
      expect(
        LpgErrorCopy.of(ErrorKind.server, hasCode: true).message,
        contains('code shown below'),
      );
      expect(
        LpgErrorCopy.of(ErrorKind.server).message,
        isNot(contains('code')),
      );
    });

    test('a refusal or a missing thing has no Retry', () {
      for (final kind in [
        ErrorKind.forbidden,
        ErrorKind.agencyBlocked,
        ErrorKind.notFound,
        ErrorKind.sessionExpired,
      ]) {
        expect(LpgErrorCopy.of(kind).retryable, isFalse, reason: '$kind');
      }
      expect(LpgErrorCopy.of(ErrorKind.offline).retryable, isTrue);
    });
  });

  group('skeleton blocks', () {
    testWidgets('a group is one shimmer however many blocks it holds', (
      tester,
    ) async {
      await tester.pumpWidget(
        _host(
          const LpgSkeletonGroup(
            children: [
              LpgSkeletonHero(),
              LpgSkeletonTileGrid(columns: 2, rows: 3),
              LpgSkeletonCard(),
            ],
          ),
        ),
      );

      expect(find.byType(LpgShimmer), findsOneWidget);
      // 1 hero + 6 tiles + 3 card lines.
      expect(find.byType(LpgSkeleton), findsNWidgets(10));
      expect(tester.takeException(), isNull);
    });

    testWidgets('the sweep stops under reduce motion (no running ticker)', (
      tester,
    ) async {
      await tester.pumpWidget(
        MediaQuery(
          data: const MediaQueryData(disableAnimations: true),
          child: _host(const LpgSkeletonGroup(children: [LpgSkeletonHero()])),
        ),
      );

      // pumpAndSettle only returns when nothing is animating.
      await tester.pumpAndSettle();
      expect(find.byType(LpgShimmer), findsOneWidget);
    });
  });
}
