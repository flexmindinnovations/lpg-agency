import 'package:api_client/api_client.dart';
import 'package:auth/auth.dart';
import 'package:core/core.dart';

/// Roles that belong to the Customer and Driver apps. The server refuses them
/// here; this covers a server that does not do so yet.
const nonStaffRoles = {'customer', 'driver'};

// Each refusal reads exactly like the server's ordinary one. Saying what kind
// of account it is would tell a stranger that the account exists.
const _badPassword = Failure(
  message: 'Email or password is incorrect.',
  errorCode: 'INVALID_CREDENTIALS',
);
const _unknownNumber = Failure(
  message: 'No account is associated with this number.',
  errorCode: 'INVALID_CREDENTIALS',
);
const _deadSession = Failure(
  message: 'Session expired or invalid. Please log in again.',
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
