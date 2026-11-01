import 'package:flutter/widgets.dart';

/// Per-action busy state for screens and sheets with more than one async
/// action.
///
/// One shared `_busy` flag makes every button show a spinner when any of
/// them is tapped. Instead, give each action a key:
///
/// ```dart
/// class _State extends State<W> with LpgBusyActions<W> {
///   Future<void> _save() => runBusy('save', () async { ... });
///
///   LpgButton(
///     label: 'Save',
///     isLoading: isBusy('save'),       // spinner only on the tapped button
///     onPressed: anyBusy ? null : _save, // others disabled meanwhile
///   )
/// }
/// ```
///
/// [runBusy] ignores a second call while any action is running (double-tap
/// safe), clears the state in a `finally` so an exception can't leave the
/// screen stuck, and skips `setState` once the widget is disposed.
mixin LpgBusyActions<T extends StatefulWidget> on State<T> {
  String? _busyAction;

  /// True while any action is running.
  bool get anyBusy => _busyAction != null;

  /// True only while the action with this [key] is running.
  bool isBusy(String key) => _busyAction == key;

  /// Runs [body] as action [key]. Returns null without running when another
  /// action is already in flight.
  Future<R?> runBusy<R>(String key, Future<R> Function() body) async {
    if (_busyAction != null) return null;
    setState(() => _busyAction = key);
    try {
      return await body();
    } finally {
      if (mounted) setState(() => _busyAction = null);
    }
  }
}
