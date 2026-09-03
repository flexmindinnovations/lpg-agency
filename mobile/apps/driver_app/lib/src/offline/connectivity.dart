import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:sync_engine/sync_engine.dart';

/// The device connectivity monitor. Overridden in tests with a fake.
final connectivityMonitorProvider = Provider<ConnectivityMonitor>(
  (ref) => PluginConnectivityMonitor(),
);

/// `true` while the device has a network interface up, `false` otherwise —
/// seeded with the current state, then following change events. Drives the
/// [OfflineBanner] and (via `SyncCoordinator`) the queue drain.
///
/// Reachability only: `true` means "an interface is up", not "the backend
/// answered". The default while unknown is `true`, so the banner never
/// flashes on a cold start.
final connectivityProvider = StreamProvider<bool>((ref) async* {
  final monitor = ref.watch(connectivityMonitorProvider);
  // The plugin throws `MissingPluginException` in a plain `flutter test` VM,
  // and reachability is best-effort anyway — fall back to "online" so the
  // banner stays hidden rather than erroring.
  try {
    yield await monitor.isOnline;
  } catch (_) {
    yield true;
  }
  yield* monitor.onConnectivityChanged.handleError((Object _) {});
});
