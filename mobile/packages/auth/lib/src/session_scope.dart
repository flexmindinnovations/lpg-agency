import 'package:flutter/widgets.dart';

import 'auth_state.dart';

/// Gives the app a fresh state tree every time a signed-in session ends.
///
/// Riverpod providers live as long as their `ProviderScope`, which for the
/// whole run of the app would be across sign-outs. Without this, the next
/// person to sign in on the same phone could see the previous person's cached
/// screens (an order list, the dashboard numbers) until each one refreshed, or
/// see a stale error. [builder] receives a [Key] that changes whenever the
/// session goes from signed in to signed out (a log out, or a session that
/// expired); put it on the `ProviderScope` so every provider, and every
/// screen's own state, is discarded and rebuilt.
///
/// The key does **not** change when the app first starts up and finds no
/// session, only when a signed-in session ends.
class SessionScope extends StatefulWidget {
  const SessionScope({
    super.key,
    required this.authController,
    required this.builder,
  });

  final AuthController authController;

  /// Builds the app tree; apply [sessionKey] to the `ProviderScope`.
  final Widget Function(BuildContext context, Key sessionKey) builder;

  @override
  State<SessionScope> createState() => _SessionScopeState();
}

class _SessionScopeState extends State<SessionScope> {
  int _epoch = 0;
  late bool _wasSignedIn;

  @override
  void initState() {
    super.initState();
    _wasSignedIn = widget.authController.state.isAuthenticated;
    widget.authController.addListener(_onAuthChanged);
  }

  @override
  void didUpdateWidget(SessionScope old) {
    super.didUpdateWidget(old);
    if (old.authController != widget.authController) {
      old.authController.removeListener(_onAuthChanged);
      _wasSignedIn = widget.authController.state.isAuthenticated;
      widget.authController.addListener(_onAuthChanged);
    }
  }

  @override
  void dispose() {
    widget.authController.removeListener(_onAuthChanged);
    super.dispose();
  }

  void _onAuthChanged() {
    final status = widget.authController.state.status;
    final signedIn = status == AuthStatus.authenticated;
    final ended = _wasSignedIn && status == AuthStatus.unauthenticated;
    _wasSignedIn = signedIn;
    if (ended) setState(() => _epoch++);
  }

  @override
  Widget build(BuildContext context) =>
      widget.builder(context, ValueKey<int>(_epoch));
}
