import 'package:flutter/scheduler.dart';

import 'auth_state.dart';

/// Opens in-app routes from push-notification taps once the session is
/// ready.
///
/// A tap that cold-starts the app (or arrives while the session is still
/// being restored, or after a sign-out) used to be thrown away: the router's
/// auth redirect sends every route to splash/login while the status is not
/// `authenticated`, and nothing remembered where the tap wanted to go. The
/// gate holds the latest tapped route and opens it as soon as the session is
/// authenticated. The newest tap wins; a route is opened at most once.
class DeepLinkGate {
  DeepLinkGate({
    required AuthController auth,
    required void Function(String route) open,
  }) {
    _auth = auth;
    _open = open;
    auth.addListener(_onAuthChanged);
  }

  late final AuthController _auth;
  late final void Function(String route) _open;
  String? _pending;
  bool _disposed = false;

  /// The route waiting for a signed-in session, if any.
  String? get pending => _pending;

  /// Opens [route] now when signed in; otherwise remembers it.
  void open(String route) {
    _pending = route;
    _flush();
  }

  void _onAuthChanged() => _flush();

  void _flush() {
    final route = _pending;
    if (route == null || _disposed) return;
    if (_auth.state.status != AuthStatus.authenticated) return;
    _pending = null;
    // After the frame, so the router's own login/splash redirect (which
    // listens to the same controller) has settled before we navigate.
    SchedulerBinding.instance.addPostFrameCallback((_) {
      if (!_disposed) _open(route);
    });
    SchedulerBinding.instance.ensureVisualUpdate();
  }

  void dispose() {
    _disposed = true;
    _auth.removeListener(_onAuthChanged);
  }
}
