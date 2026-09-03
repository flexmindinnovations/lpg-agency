import 'dart:async';

import 'package:connectivity_plus/connectivity_plus.dart';

/// Tells [SyncCoordinator] when the device (re)gains a network connection so
/// it can drain the queue immediately instead of waiting for the next poll.
///
/// An interface, not a concrete class, so tests inject a controllable stream
/// and the app injects [PluginConnectivityMonitor] (backed by
/// `connectivity_plus`). Reachability only — a `true` here means "an
/// interface is up", not "the backend answered"; the retry/backoff loop in
/// [SyncCoordinator] is still the real safety net.
abstract interface class ConnectivityMonitor {
  /// Emits `true` when connectivity is gained, `false` when lost. Distinct —
  /// no repeat of the same value.
  Stream<bool> get onConnectivityChanged;

  /// The current state — for seeding a UI before the first change event.
  Future<bool> get isOnline;
}

/// [ConnectivityMonitor] backed by the `connectivity_plus` plugin.
class PluginConnectivityMonitor implements ConnectivityMonitor {
  PluginConnectivityMonitor([Connectivity? connectivity])
    : _connectivity = connectivity ?? Connectivity();

  final Connectivity _connectivity;

  @override
  Stream<bool> get onConnectivityChanged => _connectivity.onConnectivityChanged
      .map(_hasConnection)
      .distinct();

  @override
  Future<bool> get isOnline async =>
      _hasConnection(await _connectivity.checkConnectivity());

  static bool _hasConnection(List<ConnectivityResult> results) =>
      results.any((r) => r != ConnectivityResult.none);
}
