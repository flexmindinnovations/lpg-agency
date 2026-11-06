import 'package:api_client/api_client.dart';
import 'package:auth/auth.dart';
import 'package:core/core.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';

const _principal = Principal(
  userId: 'u1',
  tenantId: 't1',
  role: 'admin',
  permissions: {},
);

class _Repo implements AuthRepository {
  _Repo({this.restore});

  Result<Principal>? restore;

  @override
  String? accessToken;

  @override
  Future<Result<Principal>> restoreSession() async =>
      restore ??
      const FailureResult(Failure(message: 'none', errorCode: 'NO_SESSION'));

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

  @override
  Future<void> logout() async {}
}

/// Holds one piece of "screen state" that a state-tree rebuild would discard.
class _Probe extends StatefulWidget {
  const _Probe();

  @override
  State<_Probe> createState() => _ProbeState();
}

class _ProbeState extends State<_Probe> {
  static int created = 0;
  final int id = ++created;

  @override
  Widget build(BuildContext context) => Text('state $id');
}

Widget _host(AuthController auth, List<Key> keys) => Directionality(
  textDirection: TextDirection.ltr,
  child: SessionScope(
    authController: auth,
    builder: (context, key) {
      keys.add(key);
      return KeyedSubtree(key: key, child: const _Probe());
    },
  ),
);

/// Lets the controller's start-up restore finish (real async, outside the
/// widget tester's fake clock).
Future<void> _settle(WidgetTester tester) => tester.runAsync(
  () => Future<void>.delayed(const Duration(milliseconds: 20)),
);

void main() {
  setUp(() => _ProbeState.created = 0);

  testWidgets('signing out discards everything under the scope', (
    tester,
  ) async {
    final auth = AuthController(_Repo(restore: const Success(_principal)));
    await _settle(tester);
    final keys = <Key>[];

    await tester.pumpWidget(_host(auth, keys));
    expect(find.text('state 1'), findsOneWidget);

    await auth.logout();
    await tester.pump();

    expect(find.text('state 2'), findsOneWidget, reason: 'rebuilt, not reused');
    expect(keys.last, isNot(keys.first));
  });

  testWidgets('a session that expires mid-use discards it too', (tester) async {
    final auth = AuthController(_Repo(restore: const Success(_principal)));
    await _settle(tester);

    await tester.pumpWidget(_host(auth, []));
    auth.handleSessionExpired();
    await tester.pump();

    expect(find.text('state 2'), findsOneWidget);
  });

  testWidgets('finding no session at start-up does not rebuild anything', (
    tester,
  ) async {
    final auth = AuthController(_Repo()); // restore fails: signed out
    final keys = <Key>[];
    await tester.pumpWidget(_host(auth, keys));
    await _settle(tester);
    await tester.pump();

    expect(find.text('state 1'), findsOneWidget);
    expect(keys.toSet(), hasLength(1));
  });

  testWidgets('signing in does not rebuild, and a second sign-out does '
      'again', (tester) async {
    final auth = AuthController(_Repo());
    await _settle(tester);
    await tester.pumpWidget(_host(auth, []));

    await auth.login(email: 'a@b.c', password: 'x');
    await tester.pump();
    expect(find.text('state 1'), findsOneWidget);

    await auth.logout();
    await tester.pump();
    expect(find.text('state 2'), findsOneWidget);

    await auth.login(email: 'd@e.f', password: 'x');
    await auth.logout();
    await tester.pump();
    expect(find.text('state 3'), findsOneWidget);
  });
}
