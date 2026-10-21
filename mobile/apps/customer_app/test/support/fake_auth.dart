import 'package:api_client/api_client.dart';
import 'package:auth/auth.dart';
import 'package:core/core.dart';

const fakeCustomerPrincipal = Principal(
  userId: 'user-1',
  tenantId: 'tenant-1',
  role: 'customer',
  permissions: {},
);

/// A signed-in [AuthRepository] that records whether [logout] ran.
class RecordingAuthRepository implements AuthRepository {
  bool loggedOut = false;

  @override
  String? accessToken = 'fake-access-token';

  @override
  Future<Result<Principal>> login({
    required String email,
    required String password,
  }) async => const Success(fakeCustomerPrincipal);

  @override
  Future<Result<void>> requestOtp({
    required String tenantId,
    required String phoneNumber,
  }) async => const Success(null);

  @override
  Future<Result<Principal>> verifyOtp({
    required String tenantId,
    required String phoneNumber,
    required String code,
  }) async => const Success(fakeCustomerPrincipal);

  @override
  Future<Result<Principal>> restoreSession() async =>
      const Success(fakeCustomerPrincipal);

  @override
  Future<Result<void>> requestPasswordReset({required String email}) async =>
      const Success(null);

  @override
  Future<Result<void>> confirmPasswordReset({
    required String resetToken,
    required String newPassword,
  }) async => const Success(null);

  @override
  Future<void> logout() async => loggedOut = true;
}
