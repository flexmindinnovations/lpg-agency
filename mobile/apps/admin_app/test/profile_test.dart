import 'dart:convert';
import 'dart:typed_data';

import 'package:admin_app/src/features/profile/data/profile_photo.dart';
import 'package:admin_app/src/features/profile/data/profile_provider.dart';
import 'package:admin_app/src/features/profile/presentation/edit_profile_sheet.dart';
import 'package:admin_app/src/features/profile/presentation/profile_avatar_button.dart';
import 'package:admin_app/src/features/profile/presentation/profile_screen.dart';
import 'package:admin_app/src/providers.dart';
import 'package:api_client/api_client.dart';
import 'package:design_system/design_system.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:image_picker/image_picker.dart';

/// Answers `/auth/me/profile` and records what was PATCHed, and the picture
/// that was uploaded or removed.
class _ProfileAdapter implements HttpClientAdapter {
  _ProfileAdapter({this.failWith});

  /// A server message to answer a save with (422), or `null` to accept it.
  final String? failWith;
  final patches = <Map<String, dynamic>>[];

  /// The pictures sent: `(filename, content type, byte count)`.
  final uploads = <(String?, String, int)>[];
  var removals = 0;

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    if (options.path == '/api/v1/auth/me/avatar') {
      if (failWith != null) {
        return _json({
          'error_code': 'VALIDATION_ERROR',
          'detail': failWith,
        }, 422);
      }
      if (options.method == 'DELETE') {
        removals++;
        return _json(_profileJson(null), 200);
      }
      final file = (options.data as FormData).files.single.value;
      uploads.add((file.filename, file.contentType.toString(), file.length));
      return _json(_profileJson('https://files.test/me.png?sig=1'), 200);
    }
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

  Map<String, dynamic> _profileJson(String? avatarUrl) => {
    'user_id': 'u1',
    'email': 'admin@example.com',
    'role': 'agency_admin',
    'display_name': 'Asha Rao',
    'contact_phone': '+91 98765 43210',
    'avatar_url': avatarUrl,
  };

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

const _profileWithPicture = AdminProfile(
  displayName: 'Asha Rao',
  ownName: 'Asha Rao',
  role: 'agency_admin',
  email: 'admin@example.com',
  agencyName: 'Dev Agency',
  contactPhone: '+91 98765 43210',
  avatarUrl: 'https://files.test/me.png?sig=0',
);

Widget _host(
  Widget home, {
  _ProfileAdapter? adapter,
  AdminProfile profile = _profile,
  ImagePicker? picker,
}) {
  final dio = Dio()..httpClientAdapter = adapter ?? _ProfileAdapter();
  return ProviderScope(
    overrides: [
      authApiProvider.overrideWithValue(AuthApi(dio)),
      adminProfileProvider.overrideWith((ref) async => profile),
      if (picker != null) profilePhotoPickerProvider.overrideWithValue(picker),
    ],
    child: MaterialApp(theme: LpgTheme.light, home: home),
  );
}

/// Hands back whatever bytes it was given, as the picked picture.
class _FakePicker implements ImagePicker {
  _FakePicker(this.bytes, {this.name = 'photo.png'});

  final List<int> bytes;
  final String name;
  final sources = <ImageSource>[];

  @override
  Future<XFile?> pickImage({
    required ImageSource source,
    double? maxWidth,
    double? maxHeight,
    int? imageQuality,
    CameraDevice preferredCameraDevice = CameraDevice.rear,
    bool requestFullMetadata = true,
  }) async {
    sources.add(source);
    return XFile.fromData(Uint8List.fromList(bytes), name: name);
  }

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

final _png = <int>[0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A, 1, 2, 3, 4];

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

  group('pictureKind', () {
    test('recognises the four picture types from their own bytes', () {
      expect(pictureKind(_png)?.contentType, 'image/png');
      expect(
        pictureKind([0xFF, 0xD8, 0xFF, 0xE0, 0, 0])?.contentType,
        'image/jpeg',
      );
      expect(
        pictureKind([
          ...'RIFF'.codeUnits,
          0,
          0,
          0,
          0,
          ...'WEBP'.codeUnits,
        ])?.contentType,
        'image/webp',
      );
      expect(
        pictureKind([0, 0, 0, 24, ...'ftypheic'.codeUnits])?.contentType,
        'image/heic',
      );
    });

    test('refuses anything else, including empty and too-short input', () {
      expect(pictureKind('<html></html>'.codeUnits), isNull);
      expect(pictureKind('%PDF-1.4'.codeUnits), isNull);
      expect(pictureKind(const []), isNull);
      expect(pictureKind(const [0xFF, 0xD8]), isNull);
    });
  });

  group('profile picture', () {
    Future<void> openOptions(WidgetTester tester) async {
      await tester.tap(find.byType(ProfileAvatarButton));
      await tester.pumpAndSettle();
    }

    testWidgets('tapping the avatar offers camera and gallery, not Remove', (
      tester,
    ) async {
      tester.view.physicalSize = const Size(400, 900);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.reset);
      await tester.pumpWidget(_host(const ProfileScreen()));
      await tester.pumpAndSettle();

      await openOptions(tester);

      expect(find.text('Take photo'), findsOneWidget);
      expect(find.text('Choose from gallery'), findsOneWidget);
      expect(find.text('Remove photo'), findsNothing);
    });

    testWidgets('a picked picture is uploaded with its real type', (
      tester,
    ) async {
      tester.view.physicalSize = const Size(400, 900);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.reset);
      final adapter = _ProfileAdapter();
      final picker = _FakePicker(_png);
      await tester.pumpWidget(
        _host(const ProfileScreen(), adapter: adapter, picker: picker),
      );
      await tester.pumpAndSettle();

      await openOptions(tester);
      await tester.tap(find.text('Choose from gallery'));
      await tester.pumpAndSettle();

      expect(picker.sources, [ImageSource.gallery]);
      expect(adapter.uploads, [('profile.png', 'image/png', _png.length)]);
      expect(find.text('Profile picture updated.'), findsOneWidget);
    });

    testWidgets('the camera option uses the camera', (tester) async {
      tester.view.physicalSize = const Size(400, 900);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.reset);
      final picker = _FakePicker(_png);
      await tester.pumpWidget(_host(const ProfileScreen(), picker: picker));
      await tester.pumpAndSettle();

      await openOptions(tester);
      await tester.tap(find.text('Take photo'));
      await tester.pumpAndSettle();

      expect(picker.sources, [ImageSource.camera]);
    });

    testWidgets('a file that is not a picture is explained and not sent', (
      tester,
    ) async {
      tester.view.physicalSize = const Size(400, 900);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.reset);
      final adapter = _ProfileAdapter();
      await tester.pumpWidget(
        _host(
          const ProfileScreen(),
          adapter: adapter,
          picker: _FakePicker('<html></html>'.codeUnits, name: 'me.jpg'),
        ),
      );
      await tester.pumpAndSettle();

      await openOptions(tester);
      await tester.tap(find.text('Choose from gallery'));
      await tester.pumpAndSettle();

      expect(find.textContaining('Choose a JPEG, PNG'), findsOneWidget);
      expect(adapter.uploads, isEmpty);
    });

    testWidgets("shows the server's reason when the picture is refused", (
      tester,
    ) async {
      tester.view.physicalSize = const Size(400, 900);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.reset);
      await tester.pumpWidget(
        _host(
          const ProfileScreen(),
          adapter: _ProfileAdapter(failWith: 'The picture is too large.'),
          picker: _FakePicker(_png),
        ),
      );
      await tester.pumpAndSettle();

      await openOptions(tester);
      await tester.tap(find.text('Choose from gallery'));
      await tester.pumpAndSettle();

      expect(find.text('The picture is too large.'), findsOneWidget);
      expect(find.text('Profile picture updated.'), findsNothing);
    });

    testWidgets('with a picture set, Remove photo deletes it', (tester) async {
      tester.view.physicalSize = const Size(400, 900);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.reset);
      final adapter = _ProfileAdapter();
      await tester.pumpWidget(
        _host(
          const ProfileScreen(),
          adapter: adapter,
          profile: _profileWithPicture,
        ),
      );
      await tester.pumpAndSettle();

      await openOptions(tester);
      await tester.tap(find.text('Remove photo'));
      await tester.pumpAndSettle();

      expect(adapter.removals, 1);
      expect(find.text('Profile picture removed.'), findsOneWidget);
    });

    testWidgets('backing out of the options changes nothing', (tester) async {
      tester.view.physicalSize = const Size(400, 900);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.reset);
      final adapter = _ProfileAdapter();
      final picker = _FakePicker(_png);
      await tester.pumpWidget(
        _host(const ProfileScreen(), adapter: adapter, picker: picker),
      );
      await tester.pumpAndSettle();

      await openOptions(tester);
      await tester.tapAt(const Offset(200, 20)); // the scrim above the sheet
      await tester.pumpAndSettle();

      expect(picker.sources, isEmpty);
      expect(adapter.uploads, isEmpty);
      expect(adapter.removals, 0);
    });
  });
}
