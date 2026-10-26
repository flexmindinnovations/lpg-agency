import 'package:api_client/api_client.dart';
import 'package:auth/auth.dart';
import 'package:core/core.dart';

/// Roles that belong to the Customer and Driver apps. Phone-OTP sign-in
/// resolves whichever account owns the number, so a customer's or driver's
/// number signs in successfully here but every admin screen then answers 403
/// or "not found".
const nonStaffRoles = {'customer', 'driver'};

/// Wraps [AuthRepository] so the admin app only ever holds a staff session:
/// a customer or driver account is signed out again (also when a stored
/// session is restored) with a message saying which app to use instead.
final class StaffOnlyAuthRepository implements AuthRepository {
  StaffOnlyAuthRepository(this._inner);

  final AuthRepository _inner;

  @override
  String? get accessToken => _inner.accessToken;

  @override
  Future<Result<Principal>> login({
    required String email,
    required String password,
  }) async => _staffOnly(await _inner.login(email: email, password: password));

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
  );

  @override
  Future<Result<Principal>> restoreSession() async =>
      _staffOnly(await _inner.restoreSession());

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

  Future<Result<Principal>> _staffOnly(Result<Principal> result) async {
    if (result case Success(
      :final value,
    ) when nonStaffRoles.contains(value.role)) {
      await _inner.logout();
      final app = value.role == 'driver' ? 'Driver' : 'Customer';
      return FailureResult(
        Failure(
          message:
              'This number belongs to a ${value.role} account. Sign in to the '
              '$app app, or use a staff login (email and password) here.',
          errorCode: 'NOT_STAFF',
        ),
      );
    }
    return result;
  }
}
