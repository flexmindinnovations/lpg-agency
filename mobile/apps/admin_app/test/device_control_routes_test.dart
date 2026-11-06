import 'package:admin_app/src/auth_provider.dart';
import 'package:admin_app/src/device_provider.dart';
import 'package:admin_app/src/router.dart';
import 'package:api_client/api_client.dart';
import 'package:auth/auth.dart';
import 'package:core/core.dart';
import 'package:design_system/design_system.dart';
import 'package:device_identity/device_identity.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'support/device_test_support.dart';

const _principal = Principal(
  userId: 'u1',
  tenantId: 't1',
  role: 'agency_admin',
  permissions: {},
);

class _Repository implements AuthRepository {
  _Repository({this.signedIn = true});

  final bool signedIn;

  @override
  String? get accessToken => 'token';

  @override
  Future<Result<Principal>> restoreSession() async => signedIn
      ? const Success(_principal)
      : const FailureResult(Failure(message: 'none', errorCode: 'NO_SESSION'));

  @override
  Future<void> logout() async {}

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

class _Host extends ConsumerWidget {
  const _Host();

  @override
  Widget build(BuildContext context, WidgetRef ref) => MaterialApp.router(
    theme: LpgTheme.light,
    routerConfig: ref.watch(routerProvider),
  );
}

Widget _app(DeviceControl device, {bool signedIn = true}) => ProviderScope(
  overrides: [
    authControllerProvider.overrideWithValue(
      AuthController(_Repository(signedIn: signedIn)),
    ),
    deviceControlProvider.overrideWithValue(device),
  ],
  child: const _Host(),
);

void main() {
  testWidgets(
    'a waiting Admin app phone sees the waiting screen with the dashboard hint',
    (tester) async {
      final device = await testDeviceControl(refusal: 'DEVICE_PENDING');

      await tester.pumpWidget(_app(device));
      await tester.pumpAndSettle();

      expect(find.text('Waiting for approval'), findsOneWidget);
      expect(find.textContaining('Settings > Linked Devices'), findsOneWidget);
      expect(find.text('Van 2 phone'), findsOneWidget);
    },
  );

  testWidgets('a blocked Admin app phone is told to ask the agency owner', (
    tester,
  ) async {
    final device = await testDeviceControl(refusal: 'DEVICE_BLOCKED');

    await tester.pumpWidget(_app(device));
    await tester.pumpAndSettle();

    expect(find.text('This phone is blocked'), findsOneWidget);
    expect(find.textContaining('agency owner'), findsOneWidget);
    // The Admin app has no offline queue, so no "saved deliveries" note.
    expect(find.textContaining('Do not delete the app'), findsNothing);
  });

  testWidgets('an unnamed phone is asked for a name before sign-in', (
    tester,
  ) async {
    final device = await testDeviceControl(savedName: null);

    await tester.pumpWidget(_app(device, signedIn: false));
    await tester.pumpAndSettle();

    expect(find.text('Name this phone'), findsOneWidget);
    expect(find.text('Save name'), findsOneWidget);
  });
}
