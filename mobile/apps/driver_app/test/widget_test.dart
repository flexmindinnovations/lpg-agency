import 'dart:async';

import 'package:api_client/api_client.dart';
import 'package:auth/auth.dart';
import 'package:core/core.dart';
import 'package:driver_app/main.dart';
import 'package:driver_app/src/api_provider.dart';
import 'package:driver_app/src/auth_provider.dart';
import 'package:driver_app/src/features/delivery/data/active_route_provider.dart';
import 'package:driver_app/src/features/notifications/data/notifications_provider.dart';
import 'package:driver_app/src/local_database_provider.dart';
import 'package:driver_app/src/push/push_notification_service.dart';
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
  _FakeAuthRepository({
    this.restoreSessionResult = const Success(_principal),
    this.hangRestore = false,
  });

  final Result<Principal> restoreSessionResult;

  /// When true, `restoreSession()` never completes — the app stays on the
  /// splash screen (`AuthStatus.unknown`).
  final bool hangRestore;

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
  Future<Result<Principal>> restoreSession() {
    if (hangRestore) return Completer<Result<Principal>>().future;
    return Future.value(restoreSessionResult);
  }

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
    activeRouteProvider.overrideWith((ref) async => null),
    unreadNotificationCountProvider.overrideWith((ref) async => 0),
    // Never `init()`ed here, so no Firebase is touched — `DriverApp` only
    // reads `takeInitialRoute()` (null) and subscribes to `taps`.
    pushNotificationServiceProvider.overrideWithValue(
      PushNotificationService(
        NotificationApi(ApiClient(baseUrl: 'https://api.test').dio),
      ),
    ),
  ],
  child: const DriverApp(),
);

void main() {
  testWidgets('holds on the splash screen while the session restores', (
    tester,
  ) async {
    await tester.pumpWidget(
      _appWith(AuthController(_FakeAuthRepository(hangRestore: true))),
    );
    await tester.pump();

    expect(find.text('LPG Agency'), findsOneWidget);
    expect(find.byType(CircularProgressIndicator), findsOneWidget);
    expect(find.byType(NavigationBar), findsNothing);
  });

  testWidgets('an authenticated session lands on the Today tab in the shell', (
    tester,
  ) async {
    await tester.pumpWidget(_appWith(AuthController(_FakeAuthRepository())));
    await tester.pumpAndSettle();

    expect(find.byType(NavigationBar), findsOneWidget);
    expect(find.widgetWithText(AppBar, 'Today'), findsOneWidget);
    expect(find.text('No route assigned yet.'), findsOneWidget);
  });

  testWidgets('the shell exposes the four tabs', (tester) async {
    await tester.pumpWidget(_appWith(AuthController(_FakeAuthRepository())));
    await tester.pumpAndSettle();

    for (final label in ['Today', 'Deliveries', 'Alerts', 'Profile']) {
      expect(
        find.widgetWithText(NavigationDestination, label),
        findsOneWidget,
      );
    }
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

    expect(find.text('Driver Sign In'), findsOneWidget);
    expect(find.byType(NavigationBar), findsNothing);
  });
}
