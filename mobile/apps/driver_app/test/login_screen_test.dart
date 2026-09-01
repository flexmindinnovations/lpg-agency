import 'package:api_client/api_client.dart';
import 'package:auth/auth.dart';
import 'package:core/core.dart';
import 'package:design_system/design_system.dart';
import 'package:driver_app/src/auth_provider.dart';
import 'package:driver_app/src/login_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

const _principal = Principal(
  userId: 'user-1',
  tenantId: 'tenant-1',
  role: 'driver',
  permissions: {},
);

/// Records the OTP calls the screen makes and returns canned results.
class _RecordingAuthRepository implements AuthRepository {
  ({String tenantId, String phoneNumber})? requestOtpArgs;
  ({String tenantId, String phoneNumber, String code})? verifyOtpArgs;

  Result<void> requestOtpResult = const Success(null);
  Result<Principal> verifyOtpResult = const Success(_principal);

  @override
  String? accessToken;

  @override
  Future<Result<void>> requestOtp({
    required String tenantId,
    required String phoneNumber,
  }) async {
    requestOtpArgs = (tenantId: tenantId, phoneNumber: phoneNumber);
    return requestOtpResult;
  }

  @override
  Future<Result<Principal>> verifyOtp({
    required String tenantId,
    required String phoneNumber,
    required String code,
  }) async {
    verifyOtpArgs = (tenantId: tenantId, phoneNumber: phoneNumber, code: code);
    return verifyOtpResult;
  }

  @override
  Future<Result<Principal>> restoreSession() async =>
      const FailureResult(Failure(message: 'none', errorCode: 'NO_SESSION'));

  @override
  Future<Result<Principal>> login({
    required String email,
    required String password,
  }) async => const Success(_principal);

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

Widget _host(AuthController controller) => ProviderScope(
  overrides: [authControllerProvider.overrideWithValue(controller)],
  child: MaterialApp(theme: LpgTheme.light, home: const LoginScreen()),
);

Future<void> _pump(WidgetTester tester, AuthController controller) async {
  tester.view.physicalSize = const Size(1000, 2400);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.reset);
  await tester.pumpWidget(_host(controller));
  await tester.pumpAndSettle();
}

void main() {
  group('Driver LoginScreen', () {
    testWidgets('renders the themed, branded sign-in form', (tester) async {
      await _pump(tester, AuthController(_RecordingAuthRepository()));

      expect(find.text('Driver Sign In'), findsOneWidget);
      expect(find.byType(LpgCard), findsOneWidget);
      expect(find.byType(LpgTextField), findsNWidgets(2)); // agency + phone
      expect(find.byType(LpgButton), findsOneWidget);
      expect(find.text('Send Code'), findsOneWidget);
    });

    testWidgets('an empty submit shows a validation message and calls nothing', (
      tester,
    ) async {
      final repo = _RecordingAuthRepository();
      await _pump(tester, AuthController(repo));

      await tester.tap(find.text('Send Code'));
      await tester.pumpAndSettle();

      expect(find.textContaining('Agency Code and Phone number'), findsOneWidget);
      expect(repo.requestOtpArgs, isNull);
    });

    testWidgets('rejects a malformed phone number', (tester) async {
      final repo = _RecordingAuthRepository();
      await _pump(tester, AuthController(repo));

      await tester.enterText(
        find.byType(LpgTextField).first,
        'demo-agency',
      );
      await tester.enterText(find.byType(LpgTextField).last, '123');
      await tester.tap(find.text('Send Code'));
      await tester.pumpAndSettle();

      expect(find.textContaining('valid phone number'), findsOneWidget);
      expect(repo.requestOtpArgs, isNull);
    });

    testWidgets('a successful request reveals the code field', (tester) async {
      final repo = _RecordingAuthRepository();
      await _pump(tester, AuthController(repo));

      await tester.enterText(find.byType(LpgTextField).first, ' demo-agency ');
      await tester.enterText(find.byType(LpgTextField).last, ' +919999900099 ');
      await tester.tap(find.text('Send Code'));
      await tester.pumpAndSettle();

      expect(repo.requestOtpArgs, isNotNull);
      expect(repo.requestOtpArgs!.tenantId, 'demo-agency');
      expect(repo.requestOtpArgs!.phoneNumber, '+919999900099');
      expect(find.text('Verify Code'), findsOneWidget);
      expect(find.byType(LpgTextField), findsNWidgets(3));
    });

    testWidgets('verify sends the trimmed code', (tester) async {
      final repo = _RecordingAuthRepository();
      await _pump(tester, AuthController(repo));

      await tester.enterText(find.byType(LpgTextField).first, 'demo-agency');
      await tester.enterText(find.byType(LpgTextField).last, '+919999900099');
      await tester.tap(find.text('Send Code'));
      await tester.pumpAndSettle();

      await tester.enterText(find.byType(LpgTextField).last, ' 123456 ');
      await tester.tap(find.text('Verify Code'));
      await tester.pumpAndSettle();

      expect(repo.verifyOtpArgs, isNotNull);
      expect(repo.verifyOtpArgs!.code, '123456');
      expect(repo.verifyOtpArgs!.phoneNumber, '+919999900099');
    });
  });
}
