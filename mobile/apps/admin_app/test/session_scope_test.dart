// The shared-phone leak: providers outlive a sign-out, so the next person to
// sign in used to see the previous person's cached numbers. SessionScope
// remounts the ProviderScope when a signed-in session ends.
import 'dart:convert';
import 'dart:typed_data';

import 'package:admin_app/src/auth_provider.dart';
import 'package:admin_app/src/features/dashboard/data/dashboard_providers.dart';
import 'package:admin_app/src/providers.dart';
import 'package:api_client/api_client.dart';
import 'package:auth/auth.dart';
import 'package:core/core.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

const _principal = Principal(
  userId: 'u1',
  tenantId: 't1',
  role: 'admin',
  permissions: {},
);

class _Repo implements AuthRepository {
  @override
  String? accessToken;

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

  @override
  Future<void> logout() async {}
}

/// The server answers each dashboard request with the next customer count:
/// the first caller ("person A") gets 7, the second ("person B") gets 9.
class _Server implements HttpClientAdapter {
  final _counts = [7, 9];
  int calls = 0;

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async => ResponseBody.fromString(
    jsonEncode({'customer_count': _counts[calls++ % _counts.length]}),
    200,
    headers: {
      Headers.contentTypeHeader: [Headers.jsonContentType],
    },
  );

  @override
  void close({bool force = false}) {}
}

class _Numbers extends ConsumerWidget {
  const _Numbers();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final summary = ref.watch(dashboardSummaryProvider);
    return Text(
      summary.when(
        data: (s) => 'customers ${s.customerCount}',
        loading: () => 'loading',
        error: (_, _) => 'error',
      ),
    );
  }
}

void main() {
  testWidgets('the next person to sign in does not see the previous person\'s '
      'cached numbers', (tester) async {
    final auth = AuthController(_Repo());
    await tester.runAsync(
      () => Future<void>.delayed(const Duration(milliseconds: 20)),
    );
    final server = _Server();
    final dio = Dio(BaseOptions(baseUrl: 'https://api.test'))
      ..httpClientAdapter = server;

    await tester.pumpWidget(
      Directionality(
        textDirection: TextDirection.ltr,
        child: SessionScope(
          authController: auth,
          builder: (context, key) => ProviderScope(
            key: key,
            overrides: [
              authControllerProvider.overrideWithValue(auth),
              adminApiProvider.overrideWithValue(AdminApi(dio)),
            ],
            child: const _Numbers(),
          ),
        ),
      ),
    );
    await tester.pump(const Duration(milliseconds: 50));
    expect(find.text('customers 7'), findsOneWidget, reason: 'person A');

    await auth.logout();
    await tester.pump();
    await auth.login(email: 'b@agency.test', password: 'x');
    await tester.pump(const Duration(milliseconds: 50));
    await tester.pump(const Duration(milliseconds: 50));

    expect(find.text('customers 7'), findsNothing, reason: 'A\'s data is gone');
    expect(find.text('customers 9'), findsOneWidget, reason: 'person B');
    expect(server.calls, 2);
  });

  testWidgets('without the scope the cached numbers would survive (the bug)', (
    tester,
  ) async {
    final auth = AuthController(_Repo());
    await tester.runAsync(
      () => Future<void>.delayed(const Duration(milliseconds: 20)),
    );
    final server = _Server();
    final dio = Dio(BaseOptions(baseUrl: 'https://api.test'))
      ..httpClientAdapter = server;

    await tester.pumpWidget(
      Directionality(
        textDirection: TextDirection.ltr,
        child: ProviderScope(
          overrides: [
            authControllerProvider.overrideWithValue(auth),
            adminApiProvider.overrideWithValue(AdminApi(dio)),
          ],
          child: const _Numbers(),
        ),
      ),
    );
    await tester.pump(const Duration(milliseconds: 50));
    await auth.logout();
    await tester.pump();
    await auth.login(email: 'b@agency.test', password: 'x');
    await tester.pump(const Duration(milliseconds: 50));

    expect(
      find.text('customers 7'),
      findsOneWidget,
      reason: 'stale, A\'s data',
    );
    expect(server.calls, 1);
  });
}
