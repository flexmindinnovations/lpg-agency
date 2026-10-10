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

/// Records the sign-in calls the screen makes and returns canned results.
class _RecordingAuthRepository implements AuthRepository {
  ({String email, String password})? startArgs;
  ({String email, String code})? verifyArgs;

  Result<DriverLoginChallenge> startResult = const Success(
    DriverLoginChallenge(phoneHint: '*********0099', devOtp: '482913'),
  );
  Result<Principal> verifyResult = const Success(_principal);

  @override
  String? accessToken;

  @override
  Future<Result<DriverLoginChallenge>> startDriverLogin({
    required String email,
    required String password,
  }) async {
    startArgs = (email: email, password: password);
    return startResult;
  }

  @override
  Future<Result<Principal>> verifyDriverLogin({
    required String email,
    required String code,
  }) async {
    verifyArgs = (email: email, code: code);
    return verifyResult;
  }

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
      expect(find.byType(LpgTextField), findsNWidgets(2)); // email + password
      expect(find.byType(LpgButton), findsOneWidget);
      expect(find.text('Continue'), findsOneWidget);
    });

    testWidgets(
      'an empty submit shows a validation message and calls nothing',
      (tester) async {
        final repo = _RecordingAuthRepository();
        await _pump(tester, AuthController(repo));

        await tester.tap(find.text('Continue'));
        await tester.pumpAndSettle();

        expect(find.textContaining('Email and Password'), findsOneWidget);
        expect(repo.startArgs, isNull);
      },
    );

    testWidgets('a correct password reveals the code field and the dev OTP', (
      tester,
    ) async {
      final repo = _RecordingAuthRepository();
      await _pump(tester, AuthController(repo));

      await tester.enterText(
        find.byType(LpgTextField).first,
        ' e2e.driver@example.com ',
      );
      await tester.enterText(find.byType(LpgTextField).last, 'secret-pass');
      await tester.tap(find.text('Continue'));
      await tester.pumpAndSettle();

      expect(repo.startArgs, isNotNull);
      expect(repo.startArgs!.email, 'e2e.driver@example.com');
      expect(repo.startArgs!.password, 'secret-pass');
      expect(find.text('Verify Code'), findsOneWidget);
      expect(find.byType(LpgTextField), findsNWidgets(3));
      expect(find.byKey(const Key('dev-otp-code')), findsOneWidget);
      expect(find.text('482913'), findsOneWidget);
    });

    testWidgets('no dev OTP banner when the backend returns no code', (
      tester,
    ) async {
      final repo = _RecordingAuthRepository()
        ..startResult = const Success(
          DriverLoginChallenge(phoneHint: '*********0099'),
        );
      await _pump(tester, AuthController(repo));

      await tester.enterText(find.byType(LpgTextField).first, 'a@b.com');
      await tester.enterText(find.byType(LpgTextField).last, 'secret-pass');
      await tester.tap(find.text('Continue'));
      await tester.pumpAndSettle();

      expect(find.text('Verify Code'), findsOneWidget);
      expect(find.byKey(const Key('dev-otp-code')), findsNothing);
    });

    testWidgets('a wrong password shows the error and no code field', (
      tester,
    ) async {
      final repo = _RecordingAuthRepository()
        ..startResult = const FailureResult(
          Failure(message: 'Email or password is incorrect.'),
        );
      await _pump(tester, AuthController(repo));

      await tester.enterText(find.byType(LpgTextField).first, 'a@b.com');
      await tester.enterText(find.byType(LpgTextField).last, 'wrong');
      await tester.tap(find.text('Continue'));
      await tester.pumpAndSettle();

      expect(find.text('Email or password is incorrect.'), findsOneWidget);
      expect(find.text('Verify Code'), findsNothing);
      expect(find.byType(LpgTextField), findsNWidgets(2));
    });

    testWidgets('verify sends the email and the trimmed code', (tester) async {
      final repo = _RecordingAuthRepository();
      await _pump(tester, AuthController(repo));

      await tester.enterText(find.byType(LpgTextField).first, 'a@b.com');
      await tester.enterText(find.byType(LpgTextField).at(1), 'secret-pass');
      await tester.tap(find.text('Continue'));
      await tester.pumpAndSettle();

      await tester.enterText(find.byType(LpgTextField).last, ' 482913 ');
      await tester.tap(find.text('Verify Code'));
      await tester.pumpAndSettle();

      expect(repo.verifyArgs, isNotNull);
      expect(repo.verifyArgs!.email, 'a@b.com');
      expect(repo.verifyArgs!.code, '482913');
    });
  });
}
