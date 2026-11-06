import 'dart:convert';
import 'dart:typed_data';

import 'package:admin_app/src/features/profile/data/profile_provider.dart';
import 'package:admin_app/src/features/profile/presentation/edit_profile_sheet.dart';
import 'package:admin_app/src/features/profile/presentation/profile_screen.dart';
import 'package:admin_app/src/providers.dart';
import 'package:api_client/api_client.dart';
import 'package:design_system/design_system.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

/// Answers `/auth/me/profile` and records what was PATCHed.
class _ProfileAdapter implements HttpClientAdapter {
  _ProfileAdapter({this.failWith});

  /// A server message to answer a save with (422), or `null` to accept it.
  final String? failWith;
  final patches = <Map<String, dynamic>>[];

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    if (options.method == 'PATCH') {
      if (failWith != null) {
        return _json({
          'error_code': 'VALIDATION_ERROR',
          'detail': failWith,
        }, 422);
      }
      final body = Map<String, dynamic>.from(options.data as Map);
      patches.add(body);
      return _json({
        'user_id': 'u1',
        'email': 'admin@example.com',
        'role': 'agency_admin',
        'display_name': body['display_name'],
        'contact_phone': body['contact_phone'],
      }, 200);
    }
    if (options.path == '/api/v1/auth/me') {
      // The principal's name can lag behind an edit.
      return _json({
        'user_id': 'u1',
        'tenant_id': 't1',
        'role': 'agency_admin',
        'permissions': <String>[],
        'email': 'admin@example.com',
        'display_name': 'Old Name',
      }, 200);
    }
    if (options.path == '/api/v1/auth/me/profile') {
      return _json({
        'user_id': 'u1',
        'email': 'admin@example.com',
        'role': 'agency_admin',
        'display_name': 'Asha Rao',
        'contact_phone': '+91 98765 43210',
      }, 200);
    }
    return _json({}, 404);
  }

  ResponseBody _json(Object body, int status) => ResponseBody.fromString(
    jsonEncode(body),
    status,
    headers: {
      Headers.contentTypeHeader: [Headers.jsonContentType],
    },
  );

  @override
  void close({bool force = false}) {}
}

const _profile = AdminProfile(
  displayName: 'Asha Rao',
  ownName: 'Asha Rao',
  role: 'agency_admin',
  email: 'admin@example.com',
  agencyName: 'Dev Agency',
  contactPhone: '+91 98765 43210',
);

Widget _host(Widget home, {_ProfileAdapter? adapter}) {
  final dio = Dio()..httpClientAdapter = adapter ?? _ProfileAdapter();
  return ProviderScope(
    overrides: [
      authApiProvider.overrideWithValue(AuthApi(dio)),
      adminProfileProvider.overrideWith((ref) async => _profile),
    ],
    child: MaterialApp(theme: LpgTheme.light, home: home),
  );
}

void main() {
  group('profileProblem', () {
    test('accepts a blank phone and a normal number', () {
      expect(profileProblem(name: 'Asha', phone: ''), isNull);
      expect(profileProblem(name: 'Asha', phone: '+91 98765 43210'), isNull);
      expect(profileProblem(name: '', phone: '040-2345 6789'), isNull);
    });

    test('rejects letters and numbers that are too short', () {
      expect(profileProblem(name: 'Asha', phone: 'call me'), isNotNull);
      expect(profileProblem(name: 'Asha', phone: '12345'), isNotNull);
    });

    test('rejects a name over 120 characters', () {
      expect(profileProblem(name: 'a' * 121, phone: ''), isNotNull);
      expect(profileProblem(name: 'a' * 120, phone: ''), isNull);
    });
  });

  group('adminProfileProvider', () {
    test(
      'takes the name and phone from the profile route, not the token',
      () async {
        final dio = Dio()..httpClientAdapter = _ProfileAdapter();
        final container = ProviderContainer(
          overrides: [
            authApiProvider.overrideWithValue(AuthApi(dio)),
            adminApiProvider.overrideWithValue(AdminApi(dio)),
          ],
        );
        addTearDown(container.dispose);

        final profile = await container.read(adminProfileProvider.future);

        expect(profile.displayName, 'Asha Rao');
        expect(profile.ownName, 'Asha Rao');
        expect(profile.contactPhone, '+91 98765 43210');
        expect(profile.agencyName, isNull, reason: 'the tenant call failed');
      },
    );
  });

  group('ProfileScreen', () {
    testWidgets('has an Edit profile button and a full-width Sign Out', (
      tester,
    ) async {
      tester.view.physicalSize = const Size(400, 900);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.reset);
      await tester.pumpWidget(_host(const ProfileScreen()));
      await tester.pumpAndSettle();

      expect(find.text('Edit profile'), findsOneWidget);
      expect(find.text('+91 98765 43210'), findsOneWidget);

      final signOut = tester.getRect(
        find.ancestor(
          of: find.text('Sign Out'),
          matching: find.byType(LpgButton),
        ),
      );
      // The page has a 20 dp gutter on each side.
      expect(signOut.width, 400 - 2 * LpgSpacing.mdl);
    });
  });

  group('EditProfileSheet', () {
    testWidgets('saves both fields and closes', (tester) async {
      tester.view.physicalSize = const Size(400, 900);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.reset);
      final adapter = _ProfileAdapter();
      await tester.pumpWidget(
        _host(
          const Scaffold(body: EditProfileSheet(profile: _profile)),
          adapter: adapter,
        ),
      );

      await tester.enterText(find.byType(TextField).first, '  Asha R  ');
      await tester.tap(find.text('Save changes'));
      await tester.pumpAndSettle();

      expect(adapter.patches, [
        {'display_name': 'Asha R', 'contact_phone': '+91 98765 43210'},
      ]);
    });

    testWidgets('a bad phone is explained and nothing is sent', (tester) async {
      tester.view.physicalSize = const Size(400, 900);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.reset);
      final adapter = _ProfileAdapter();
      await tester.pumpWidget(
        _host(
          const Scaffold(body: EditProfileSheet(profile: _profile)),
          adapter: adapter,
        ),
      );

      await tester.enterText(find.byType(TextField).last, 'call me');
      await tester.tap(find.text('Save changes'));
      await tester.pumpAndSettle();

      expect(find.textContaining('digits, spaces'), findsOneWidget);
      expect(adapter.patches, isEmpty);
    });

    testWidgets("shows the server's reason when the save is refused", (
      tester,
    ) async {
      tester.view.physicalSize = const Size(400, 900);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.reset);
      await tester.pumpWidget(
        _host(
          const Scaffold(body: EditProfileSheet(profile: _profile)),
          adapter: _ProfileAdapter(failWith: 'Profile is locked.'),
        ),
      );

      await tester.tap(find.text('Save changes'));
      await tester.pumpAndSettle();

      expect(find.textContaining('Profile is locked.'), findsOneWidget);
    });
  });
}
