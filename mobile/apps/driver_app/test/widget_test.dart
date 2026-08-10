import 'package:api_client/api_client.dart';
import 'package:auth/auth.dart';
import 'package:core/core.dart';
import 'package:driver_app/main.dart';
import 'package:driver_app/src/auth_provider.dart';
import 'package:driver_app/src/local_database_provider.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:local_storage/local_storage.dart';

const _principal = Principal(
  userId: 'user-1',
  tenantId: 'tenant-1',
  role: 'driver',
  permissions: {},
);

/// A fake [AuthRepository] — `abstract interface class` makes this legal to
/// implement outside `auth`'s own library, mirroring the fake `auth`'s own
/// tests use. `routerProvider` now watches `authControllerProvider` at
/// build time (Phase 6's route guards), so every widget test needs one.
class _FakeAuthRepository implements AuthRepository {
  _FakeAuthRepository({this.restoreSessionResult = const Success(_principal)});

  final Result<Principal> restoreSessionResult;

  @override
  String? accessToken = 'fake-access-token';

  @override
  Future<Result<Principal>> login({
    required String email,
    required String password,
  }) async => const Success(_principal);

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
  }) async => const Success(_principal);

  @override
  Future<Result<Principal>> restoreSession() async => restoreSessionResult;

  @override
  Future<Result<void>> requestPasswordReset({required String email}) async =>
      const Success(null);

  @override
  Future<Result<void>> confirmPasswordReset({
    required String resetToken,
    required String newPassword,
  }) async => const Success(null);

  @override
  Future<void> logout() async {}
}

Widget _appWith(AuthController authController) => ProviderScope(
  overrides: [
    localDatabaseProvider.overrideWithValue(NoopLocalDatabase()),
    authControllerProvider.overrideWithValue(authController),
  ],
  child: const DriverApp(),
);

void main() {
  testWidgets('an authenticated session shows the home shell', (tester) async {
    await tester.pumpWidget(_appWith(AuthController(_FakeAuthRepository())));
    await tester.pumpAndSettle();

    expect(find.text('LPG Agency'), findsWidgets);
    expect(find.text('Repository foundation'), findsOneWidget);
  });

  testWidgets('shell has a Material scaffold', (tester) async {
    await tester.pumpWidget(_appWith(AuthController(_FakeAuthRepository())));
    await tester.pumpAndSettle();

    expect(find.byType(Scaffold), findsOneWidget);
  });

  testWidgets('an unauthenticated session is redirected to sign-in', (
    tester,
  ) async {
    final repository = _FakeAuthRepository(
      restoreSessionResult: const FailureResult(
        Failure(message: 'none', errorCode: 'NO_SESSION'),
      ),
    );

    await tester.pumpWidget(_appWith(AuthController(repository)));
    await tester.pumpAndSettle();

    expect(find.text('Sign in'), findsWidgets);
    expect(find.text('Repository foundation'), findsNothing);
  });
}
