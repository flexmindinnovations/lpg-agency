import 'package:api_client/api_client.dart';
import 'package:auth/auth.dart';
import 'package:core/core.dart';
import 'package:customer_app/main.dart';
import 'package:customer_app/src/auth_provider.dart';
import 'package:customer_app/src/providers.dart';
import 'package:customer_app/src/push/push_notification_service.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

const _principal = Principal(
  userId: 'user-1',
  tenantId: 'tenant-1',
  role: 'customer',
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
    authControllerProvider.overrideWithValue(authController),
    // Never `init()`ed here, so no Firebase is touched — the widget only
    // reads `takeInitialRoute()` (null) and subscribes to `taps`.
    pushNotificationServiceProvider.overrideWithValue(
      PushNotificationService(NotificationApi(Dio())),
    ),
  ],
  child: const CustomerApp(),
);

void main() {
  testWidgets('an authenticated session shows the home shell', (tester) async {
    await tester.pumpWidget(_appWith(AuthController(_FakeAuthRepository())));
    await tester.pumpAndSettle();

    expect(find.text('LPG Flow'), findsOneWidget);
    // Not asserting on the balance card's own text: it's driven by
    // `ledgerAsync` (a real, unmocked network call in this test), so
    // whether it's showing loading/data/error copy at the moment
    // `pumpAndSettle` returns isn't deterministic here. The primary action
    // button is static regardless of that card's state.
    expect(find.text('Order Gas Refill'), findsOneWidget);
  });

  testWidgets('shell has a Material scaffold', (tester) async {
    await tester.pumpWidget(_appWith(AuthController(_FakeAuthRepository())));
    await tester.pumpAndSettle();

    // One Scaffold for the AppShell (bottom nav) and one for the active
    // branch screen's own AppBar — the standard StatefulNavigationShell
    // shape, not a bug.
    expect(find.byType(Scaffold), findsWidgets);
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

    expect(find.textContaining('Sign in'), findsWidgets);
    expect(find.text('Order Gas Refill'), findsNothing);
  });
}
