import 'package:design_system/design_system.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:riverpod/riverpod.dart';

String _show(AsyncValue<int> value) => value.whenQuiet(
  loading: () => 'loading',
  error: (e, _) => 'error: $e',
  data: (v) => 'data $v',
);

/// Builds the exact states a provider passes through, by running one.
/// Synchronous on purpose: awaiting here would let the first fetch finish
/// before the test looks at the loading state.
ProviderContainer _container(
  Future<int> Function(int attempt) fetch, {
  Duration? Function(int, Object)? retry,
}) {
  var attempt = 0;
  _provider = FutureProvider<int>((ref) => fetch(attempt++));
  final container = ProviderContainer(retry: retry ?? (_, _) => null);
  addTearDown(container.dispose);
  container.listen(_provider, (_, _) {});
  return container;
}

late FutureProvider<int> _provider;

void main() {
  test('first load: loading, then data', () async {
    final container = _container((_) async => 1);

    expect(_show(container.read(_provider)), 'loading');
    await container.read(_provider.future);
    expect(_show(container.read(_provider)), 'data 1');
  });

  test('first load that fails with no retry: loading, then error', () async {
    final container = _container((_) async => throw 'boom');

    expect(_show(container.read(_provider)), 'loading');
    await expectLater(container.read(_provider.future), throwsA('boom'));
    expect(_show(container.read(_provider)), 'error: boom');
  });

  test('first load that fails and is retrying stays loading', () async {
    final container = _container(
      (attempt) async => attempt == 0 ? throw 'boom' : 7,
      retry: (n, _) => n == 0 ? const Duration(milliseconds: 10) : null,
    );

    await Future<void>.delayed(const Duration(milliseconds: 1));
    final state = container.read(_provider);
    expect(state.isLoading, isTrue);
    expect(state.hasError, isTrue, reason: 'Riverpod keeps the retried error');
    expect(_show(state), 'loading');

    await container.read(_provider.future);
    expect(_show(container.read(_provider)), 'data 7');
  });

  test('refresh keeps the old value, also while the refresh is retried and '
      'after it fails', () async {
    final container = _container(
      (attempt) async => attempt == 0 ? 1 : throw 'boom',
      retry: (n, _) => n == 0 ? const Duration(milliseconds: 10) : null,
    );
    await container.read(_provider.future);
    expect(_show(container.read(_provider)), 'data 1');

    container.invalidate(_provider);
    expect(_show(container.read(_provider)), 'data 1');

    await Future<void>.delayed(const Duration(milliseconds: 1));
    expect(_show(container.read(_provider)), 'data 1', reason: 'retrying');

    await Future<void>.delayed(const Duration(milliseconds: 50));
    final failed = container.read(_provider);
    expect(failed.hasError, isTrue);
    expect(_show(failed), 'data 1', reason: 'failed refresh');
  });
}
