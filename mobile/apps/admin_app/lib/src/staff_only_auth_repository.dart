import 'package:api_client/api_client.dart';
import 'package:auth/auth.dart';
import 'package:core/core.dart';
import 'package:flutter/widgets.dart';

import 'i18n/admin_strings.dart';

/// Roles that belong to the Customer and Driver apps. The server refuses them
/// here; this covers a server that does not do so yet.
const nonStaffRoles = {'customer', 'driver'};

// Each refusal reads exactly like the server's ordinary one. Saying what kind
// of account it is would tell a stranger that the account exists. Always the
// English catalogue: the server's refusals are English only.
final _text = adminStringsFor(const Locale('en')).signInRefused;
final _badPassword = Failure(
  message: _text.badPassword,
  errorCode: 'INVALID_CREDENTIALS',
);
final _unknownNumber = Failure(
  message: _text.unknownNumber,
  errorCode: 'INVALID_CREDENTIALS',
);
final _deadSession = Failure(
  message: _text.deadSession,
  errorCode: 'REFRESH_TOKEN_INVALID',
);

/// Wraps [AuthRepository] so the admin app only ever holds a staff session:
/// a customer or driver account is signed out again, also when a stored
/// session is restored.
final class StaffOnlyAuthRepository implements AuthRepository {
  StaffOnlyAuthRepository(this._inner);

  final AuthRepository _inner;

  @override
  String? get accessToken => _inner.accessToken;

  @override
  Future<Result<Principal>> login({
    required String email,
    required String password,
  }) async => _staffOnly(
    await _inner.login(email: email, password: password),
    _badPassword,
  );

  @override
  Future<Result<Principal>> verifyOtp({
    required String tenantId,
    required String phoneNumber,
    required String code,
  }) async => _staffOnly(
    await _inner.verifyOtp(
      tenantId: tenantId,
      phoneNumber: phoneNumber,
      code: code,
    ),
    _unknownNumber,
  );

  @override
  Future<Result<Principal>> restoreSession() async =>
      _staffOnly(await _inner.restoreSession(), _deadSession);

  @override
  Future<Result<void>> requestOtp({
    required String tenantId,
    required String phoneNumber,
  }) => _inner.requestOtp(tenantId: tenantId, phoneNumber: phoneNumber);

  @override
  Future<Result<void>> requestPasswordReset({required String email}) =>
      _inner.requestPasswordReset(email: email);

  @override
  Future<Result<void>> confirmPasswordReset({
    required String resetToken,
    required String newPassword,
  }) => _inner.confirmPasswordReset(
    resetToken: resetToken,
    newPassword: newPassword,
  );

  @override
  Future<void> logout() => _inner.logout();

  Future<Result<Principal>> _staffOnly(
    Result<Principal> result,
    Failure refusal,
  ) async {
    if (result case Success(
      :final value,
    ) when nonStaffRoles.contains(value.role)) {
      await _inner.logout();
      return FailureResult(refusal);
    }
    return result;
  }
}
