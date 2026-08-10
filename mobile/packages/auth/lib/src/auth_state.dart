import 'dart:async';

import 'package:api_client/api_client.dart';
import 'package:core/core.dart';
import 'package:flutter/foundation.dart';

import 'auth_repository.dart';

enum AuthStatus { unknown, authenticated, unauthenticated }

/// Snapshot of the current session — `unknown` only ever during the brief
/// window between app start and [AuthController]'s startup restore
/// resolving, so a route guard has a third state to fall back on besides
/// flashing the login screen before a valid session is even checked.
class AuthSessionState {
  const AuthSessionState._({required this.status, this.principal});

  const AuthSessionState.unknown() : this._(status: AuthStatus.unknown);
  const AuthSessionState.unauthenticated()
    : this._(status: AuthStatus.unauthenticated);
  const AuthSessionState.authenticated(Principal principal)
    : this._(status: AuthStatus.authenticated, principal: principal);

  final AuthStatus status;
  final Principal? principal;

  bool get isAuthenticated => status == AuthStatus.authenticated;
}

/// Owns the current [AuthSessionState] and exposes it both as plain Dart
/// state and as a [Listenable] — the latter is what lets `go_router`'s
/// `refreshListenable` re-evaluate route guards the instant a login/logout
/// happens, no polling required. Framework-agnostic beyond `ChangeNotifier`
/// itself: no Riverpod import here — `mobile/apps/*/lib/src/auth_provider.dart`
/// is where each app wraps this in a `Provider<AuthController>`, exactly
/// mirroring `local_database_provider.dart`'s pattern.
class AuthController extends ChangeNotifier {
  AuthController(this._repository) {
    // Fire-and-forget: `state` starts at `unknown`, `restoreSession()`'s
    // result lands via `notifyListeners()` whichever way it resolves — a
    // route guard checking `state.status == unknown` covers the gap.
    unawaited(_restoreOnStartup());
  }

  final AuthRepository _repository;
  AuthSessionState _state = const AuthSessionState.unknown();

  AuthSessionState get state => _state;

  Future<Result<Principal>> login({
    required String email,
    required String password,
  }) async {
    final result = await _repository.login(email: email, password: password);
    _apply(result);
    return result;
  }

  Future<Result<void>> requestOtp({
    required String tenantId,
    required String phoneNumber,
  }) => _repository.requestOtp(tenantId: tenantId, phoneNumber: phoneNumber);

  Future<Result<Principal>> verifyOtp({
    required String tenantId,
    required String phoneNumber,
    required String code,
  }) async {
    final result = await _repository.verifyOtp(
      tenantId: tenantId,
      phoneNumber: phoneNumber,
      code: code,
    );
    _apply(result);
    return result;
  }

  Future<Result<void>> requestPasswordReset({required String email}) =>
      _repository.requestPasswordReset(email: email);

  Future<Result<void>> confirmPasswordReset({
    required String resetToken,
    required String newPassword,
  }) => _repository.confirmPasswordReset(
    resetToken: resetToken,
    newPassword: newPassword,
  );

  Future<void> logout() async {
    await _repository.logout();
    _state = const AuthSessionState.unauthenticated();
    notifyListeners();
  }

  /// Wired into `ApiClient.onSessionExpired` — a failed silent refresh means
  /// the session is gone; route guards must react immediately, not wait for
  /// the next navigation attempt to discover it.
  void handleSessionExpired() {
    if (_state.status == AuthStatus.unauthenticated) return;
    _state = const AuthSessionState.unauthenticated();
    notifyListeners();
  }

  /// Redeems the persisted refresh token, if any — the same operation
  /// `ApiClient`'s `refreshAccessToken` callback drives, exposed here too
  /// so `main()` can wire both to one shared implementation.
  Future<Result<Principal>> restoreSession() async {
    final result = await _repository.restoreSession();
    _apply(result);
    return result;
  }

  String? get accessToken => _repository.accessToken;

  Future<void> _restoreOnStartup() => restoreSession();

  void _apply(Result<Principal> result) {
    _state = result.when(
      onSuccess: AuthSessionState.authenticated,
      onFailure: (_) => const AuthSessionState.unauthenticated(),
    );
    notifyListeners();
  }
}
