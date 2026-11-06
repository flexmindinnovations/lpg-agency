import 'dart:async';

import 'package:api_client/api_client.dart';
import 'package:auth/auth.dart';
import 'package:core/core.dart';
import 'package:driver_app/main.dart';
import 'package:driver_app/src/api_provider.dart';
import 'package:driver_app/src/auth_provider.dart';
import 'package:driver_app/src/device_provider.dart';
import 'package:device_identity/device_identity.dart';
import 'package:driver_app/src/features/delivery/data/active_route_provider.dart';
import 'package:driver_app/src/features/notifications/data/notifications_provider.dart';
import 'package:driver_app/src/local_database_provider.dart';
import 'package:driver_app/src/push/push_notification_service.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:local_storage/local_storage.dart';

import 'support/device_test_support.dart';

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

Widget _appWith(
  AuthController authController,
  DeviceControl device,
) => ProviderScope(
  overrides: [
    deviceControlProvider.overrideWithValue(device),
    localDatabaseProvider.overrideWithValue(NoopLocalDatabase()),
    authControllerProvider.overrideWithValue(authController),
    activeRouteProvider.overrideWith((ref) async => null),
    unreadNotificationCountProvider.overrideWith((ref) async => 0),
    notificationsRealtimeProvider.overrideWith((ref) => const Stream.empty()),
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

/// Phone-sized window: the shell shows the bottom bar below 600px wide.
void _usePhoneSize(WidgetTester tester) {
  tester.view.physicalSize = const Size(390, 844);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.reset);
}

void main() {
  testWidgets('holds on the splash screen while the session restores', (
    tester,
  ) async {
    final device = await testDeviceControl();
    await tester.pumpWidget(
      _appWith(AuthController(_FakeAuthRepository(hangRestore: true)), device),
    );
    await tester.pump();

    expect(find.text('LPG Agency'), findsOneWidget);
    expect(find.byType(LpgSplash), findsOneWidget);
    expect(find.byType(LpgNavigationBar), findsNothing);
  });

  testWidgets('an authenticated session lands on the Today tab in the shell', (
    tester,
  ) async {
    final device = await testDeviceControl();
    _usePhoneSize(tester);
    await tester.pumpWidget(
      _appWith(AuthController(_FakeAuthRepository()), device),
    );
    await tester.pumpAndSettle();

    expect(find.byType(LpgNavigationBar), findsOneWidget);
    expect(find.widgetWithText(AppBar, 'Today'), findsOneWidget);
    expect(find.text('No route assigned yet.'), findsOneWidget);
  });

  testWidgets('the shell exposes the four tabs', (tester) async {
    final device = await testDeviceControl();
    _usePhoneSize(tester);
    await tester.pumpWidget(
      _appWith(AuthController(_FakeAuthRepository()), device),
    );
    await tester.pumpAndSettle();

    for (final label in ['Today', 'Deliveries', 'Alerts', 'Profile']) {
      expect(find.byTooltip(label), findsOneWidget);
    }
  });

  testWidgets('an unauthenticated session is redirected to sign-in', (
    tester,
  ) async {
    final device = await testDeviceControl();
    final repository = _FakeAuthRepository(
      restoreSessionResult: const FailureResult(
        Failure(message: 'none', errorCode: 'NO_SESSION'),
      ),
    );

    await tester.pumpWidget(_appWith(AuthController(repository), device));
    await tester.pumpAndSettle();

    expect(find.text('Driver Sign In'), findsOneWidget);
    expect(find.byType(LpgNavigationBar), findsNothing);
  });

  group('device control (ADR-071)', () {
    testWidgets(
      'a phone that was never named is asked for a name before sign-in',
      (tester) async {
        final device = await testDeviceControl(savedName: null);
        final repository = _FakeAuthRepository(
          restoreSessionResult: const FailureResult(
            Failure(message: 'none', errorCode: 'NO_SESSION'),
          ),
        );

        await tester.pumpWidget(_appWith(AuthController(repository), device));
        await tester.pumpAndSettle();

        expect(find.text('Name this phone'), findsOneWidget);
        expect(find.text('Driver Sign In'), findsNothing);

        await tester.tap(find.text('Save name'));
        await tester.pumpAndSettle();

        expect(find.text('Driver Sign In'), findsOneWidget);
      },
    );

    testWidgets(
      'a signed-in phone that is waiting for approval sees the waiting screen',
      (tester) async {
        _usePhoneSize(tester);
        final device = await testDeviceControl(refusal: 'DEVICE_PENDING');

        await tester.pumpWidget(
          _appWith(AuthController(_FakeAuthRepository()), device),
        );
        await tester.pumpAndSettle();

        expect(find.text('Waiting for approval'), findsOneWidget);
        expect(find.text('Van 2 phone'), findsOneWidget);
        expect(find.byType(LpgNavigationBar), findsNothing);
      },
    );

    testWidgets(
      'a blocked phone sees the blocked screen and the saved-deliveries note',
      (tester) async {
        _usePhoneSize(tester);
        final device = await testDeviceControl(refusal: 'DEVICE_BLOCKED');

        await tester.pumpWidget(
          _appWith(AuthController(_FakeAuthRepository()), device),
        );
        await tester.pumpAndSettle();

        expect(find.text('This phone is blocked'), findsOneWidget);
        expect(find.textContaining('Do not delete the app'), findsOneWidget);
        expect(find.byType(LpgNavigationBar), findsNothing);
      },
    );

    testWidgets('trying again leaves the blocked screen for sign-in', (
      tester,
    ) async {
      final device = await testDeviceControl(refusal: 'DEVICE_BLOCKED');
      final repository = _FakeAuthRepository(
        restoreSessionResult: const FailureResult(
          Failure(message: 'none', errorCode: 'NO_SESSION'),
        ),
      );
      await tester.pumpWidget(_appWith(AuthController(repository), device));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Try signing in again'));
      await tester.pumpAndSettle();

      expect(find.text('Driver Sign In'), findsOneWidget);
    });

    testWidgets('an approved phone goes straight to the shell', (tester) async {
      _usePhoneSize(tester);
      final device = await testDeviceControl();

      await tester.pumpWidget(
        _appWith(AuthController(_FakeAuthRepository()), device),
      );
      await tester.pumpAndSettle();

      expect(find.byType(LpgNavigationBar), findsOneWidget);
    });
  });
}
