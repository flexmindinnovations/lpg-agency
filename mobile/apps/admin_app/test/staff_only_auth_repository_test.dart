import 'package:api_client/api_client.dart';
import 'package:auth/auth.dart';
import 'package:core/core.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:admin_app/src/staff_only_auth_repository.dart';

class _FakeRepository implements AuthRepository {
  _FakeRepository(this.role);

  final String role;
  var loggedOut = false;

  Result<Principal> get _principal => Success(
    Principal(userId: 'u1', tenantId: 't1', role: role, permissions: const {}),
  );

  @override
  String? get accessToken => 'token';

  @override
  Future<Result<Principal>> login({
    required String email,
    required String password,
  }) async => _principal;

  @override
  Future<Result<Principal>> verifyOtp({
    required String tenantId,
    required String phoneNumber,
    required String code,
  }) async => _principal;

  @override
  Future<Result<Principal>> restoreSession() async => _principal;

  @override
  Future<void> logout() async => loggedOut = true;

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

void main() {
  test('signs a customer account out again with a clear message', () async {
    final inner = _FakeRepository('customer');
    final result = await StaffOnlyAuthRepository(inner).restoreSession();

    expect(result, isA<FailureResult<Principal>>());
    final failure = (result as FailureResult<Principal>).failure;
    expect(failure.errorCode, 'NOT_STAFF');
    expect(failure.message, contains('Customer app'));
    expect(inner.loggedOut, isTrue);
  });

  test('lets a staff account through', () async {
    final inner = _FakeRepository('agency_admin');
    final result = await StaffOnlyAuthRepository(
      inner,
    ).login(email: 'a@b.c', password: 'x');

    expect(result, isA<Success<Principal>>());
    expect(inner.loggedOut, isFalse);
  });
}
