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
  for (final role in ['customer', 'driver']) {
    test('signs a $role out again without saying what it is', () async {
      final inner = _FakeRepository(role);
      final result = await StaffOnlyAuthRepository(inner).restoreSession();

      expect(result, isA<FailureResult<Principal>>());
      final failure = (result as FailureResult<Principal>).failure;
      expect(failure.errorCode, 'REFRESH_TOKEN_INVALID');
      expect(failure.message.toLowerCase(), isNot(contains(role)));
      expect(inner.loggedOut, isTrue);
    });
  }

  test('a refused password sign-in reads like a wrong password', () async {
    final result = await StaffOnlyAuthRepository(
      _FakeRepository('customer'),
    ).login(email: 'a@b.c', password: 'x');

    final failure = (result as FailureResult<Principal>).failure;
    expect(failure.message, 'Email or password is incorrect.');
    expect(failure.errorCode, 'INVALID_CREDENTIALS');
  });

  test('the other refusals use the server wording too', () async {
    final repository = StaffOnlyAuthRepository(_FakeRepository('driver'));

    final otp = await repository.verifyOtp(
      tenantId: 't1',
      phoneNumber: '+919876543210',
      code: '123456',
    );
    final restored = await repository.restoreSession();

    expect(
      (otp as FailureResult<Principal>).failure.message,
      'No account is associated with this number.',
    );
    expect(
      (restored as FailureResult<Principal>).failure.message,
      'Session expired or invalid. Please log in again.',
    );
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
