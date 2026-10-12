import 'package:api_client/api_client.dart';
import 'package:auth/auth.dart';
import 'package:core/core.dart';
import 'package:design_system/design_system.dart';
import 'package:driver_app/src/api_provider.dart';
import 'package:driver_app/src/auth_provider.dart';
import 'package:driver_app/src/features/profile/data/profile_provider.dart';
import 'package:driver_app/src/features/profile/presentation/profile_screen.dart';
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

DriverMe _me({DriverMeVehicle? vehicle}) => DriverMe(
  driverId: 'drv-1',
  name: 'Ramesh Kumar',
  phoneNumber: '+919000011111',
  licenseNumber: 'DL-9001',
  status: 'active',
  vehicle: vehicle,
);

class _RecordingAuthRepository implements AuthRepository {
  bool loggedOut = false;

  @override
  String? accessToken;

  @override
  Future<void> logout() async => loggedOut = true;

  @override
  Future<Result<Principal>> restoreSession() async => const Success(_principal);

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
  Future<Result<void>> requestPasswordReset({required String email}) async =>
      const Success(null);

  @override
  Future<Result<void>> confirmPasswordReset({
    required String resetToken,
    required String newPassword,
  }) async => const Success(null);
}

Widget _host(AuthController controller, Future<DriverMe> Function() profile) =>
    ProviderScope(
      overrides: [
        authControllerProvider.overrideWithValue(controller),
        driverProfileProvider.overrideWith((ref) => profile()),
        // Log Out also clears the offline read cache; NoopLocalDatabase makes
        // `resourceCacheProvider` null, so the clear is a safe no-op here.
        localDatabaseProvider.overrideWithValue(NoopLocalDatabase()),
        // Log Out drops the FCM token before signing out; the service is
        // never `init()`ed here so `unregister()` is a no-op.
        pushNotificationServiceProvider.overrideWithValue(
          PushNotificationService(
            NotificationApi(ApiClient(baseUrl: 'https://api.test').dio),
          ),
        ),
      ],
      child: MaterialApp(theme: LpgTheme.light, home: const ProfileScreen()),
    );

void main() {
  group('Driver ProfileScreen', () {
    testWidgets('renders the driver identity, licence and vehicle', (
      tester,
    ) async {
      await tester.pumpWidget(
        _host(
          AuthController(_RecordingAuthRepository()),
          () async => _me(
            vehicle: const DriverMeVehicle(
              registrationNumber: 'TS07UB4412',
              make: 'Tata',
              model: 'Ace',
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('Ramesh Kumar'), findsOneWidget);
      expect(find.text('+919000011111'), findsOneWidget);
      expect(find.textContaining('DL-9001'), findsOneWidget);
      expect(find.textContaining('TS07UB4412'), findsOneWidget);
      expect(find.text('Log Out'), findsOneWidget);
    });

    testWidgets('shows "Not on a route" when there is no vehicle', (
      tester,
    ) async {
      await tester.pumpWidget(
        _host(AuthController(_RecordingAuthRepository()), () async => _me()),
      );
      await tester.pumpAndSettle();

      expect(find.text('Not on a route'), findsOneWidget);
    });

    testWidgets('Log Out calls the auth controller', (tester) async {
      final repo = _RecordingAuthRepository();
      await tester.pumpWidget(_host(AuthController(repo), () async => _me()));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Log Out'));
      await tester.pumpAndSettle();

      expect(repo.loggedOut, isTrue);
    });
  });
}
