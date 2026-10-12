import 'package:api_client/api_client.dart';
import 'package:auth/auth.dart';
import 'package:core/core.dart';
import 'package:flutter_test/flutter_test.dart';

const _principal = Principal(
  userId: 'user-1',
  tenantId: 'tenant-1',
  role: 'driver',
  permissions: {'orders:deliver'},
);

/// A fake [AuthRepository] — `abstract interface class` makes this legal
/// from outside `auth`'s own library, unlike `AuthApi` (a `final class` in
/// `api_client`), matching `local_storage`'s "fakes via constructor
/// injection, no mocking framework" convention.
class _FakeAuthRepository implements AuthRepository {
  _FakeAuthRepository({this.restoreSessionResult});

  Result<Principal>? restoreSessionResult;
  Result<Principal> loginResult = const Success(_principal);
  Result<Principal> verifyOtpResult = const Success(_principal);
  int logoutCalls = 0;

  @override
  String? accessToken;

  @override
  Future<Result<Principal>> login({
    required String email,
    required String password,
  }) async => loginResult;

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
  }) async => verifyOtpResult;

  @override
  Future<Result<Principal>> restoreSession() async =>
      restoreSessionResult ??
      const FailureResult(
        Failure(message: 'No session to restore.', errorCode: 'NO_SESSION'),
      );

  @override
  Future<Result<void>> requestPasswordReset({required String email}) async =>
      const Success(null);

  @override
  Future<Result<void>> confirmPasswordReset({
    required String resetToken,
    required String newPassword,
  }) async => const Success(null);

  @override
  Future<void> logout() async {
    logoutCalls++;
  }
}

void main() {
  group('AuthController', () {
    test(
      'starts unknown, then settles to unauthenticated when startup restore fails',
      () async {
        final repository = _FakeAuthRepository();
        final controller = AuthController(repository);

        expect(controller.state.status, AuthStatus.unknown);

        await Future<void>.delayed(Duration.zero);

        expect(controller.state.status, AuthStatus.unauthenticated);
      },
    );

    test(
      'settles to authenticated when a session can be restored at startup',
      () async {
        final repository = _FakeAuthRepository(
          restoreSessionResult: const Success(_principal),
        );
        final controller = AuthController(repository);

        await Future<void>.delayed(Duration.zero);

        expect(controller.state.isAuthenticated, isTrue);
        expect(controller.state.principal, _principal);
      },
    );

    test(
      'login notifies listeners and updates state to authenticated',
      () async {
        final repository = _FakeAuthRepository(
          restoreSessionResult: const FailureResult(
            Failure(message: 'none', errorCode: 'NO_SESSION'),
          ),
        );
        final controller = AuthController(repository);
        await Future<void>.delayed(Duration.zero);

        var notifications = 0;
        controller.addListener(() => notifications++);

        final result = await controller.login(
          email: 'driver@example.com',
          password: 'correct-horse',
        );

        expect(
          result.when(onSuccess: (p) => p, onFailure: (_) => null),
          _principal,
        );
        expect(controller.state.isAuthenticated, isTrue);
        expect(notifications, 1);
      },
    );

    test('logout clears the session and notifies listeners', () async {
      final repository = _FakeAuthRepository(
        restoreSessionResult: const Success(_principal),
      );
      final controller = AuthController(repository);
      await Future<void>.delayed(Duration.zero);

      var notifications = 0;
      controller.addListener(() => notifications++);

      await controller.logout();

      expect(controller.state.status, AuthStatus.unauthenticated);
      expect(repository.logoutCalls, 1);
      expect(notifications, 1);
    });

    test(
      'handleSessionExpired transitions to unauthenticated exactly once for repeated calls',
      () async {
        final repository = _FakeAuthRepository(
          restoreSessionResult: const Success(_principal),
        );
        final controller = AuthController(repository);
        await Future<void>.delayed(Duration.zero);

        var notifications = 0;
        controller.addListener(() => notifications++);

        controller.handleSessionExpired();
        controller.handleSessionExpired();

        expect(controller.state.status, AuthStatus.unauthenticated);
        // The second call is a no-op — already unauthenticated, no need to
        // notify listeners again for the same transition.
        expect(notifications, 1);
      },
    );
  });
}
