import 'package:core/core.dart';
import 'package:device_identity/device_identity.dart';
import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart' show AppLifecycleState;
import 'package:flutter_test/flutter_test.dart';

import 'support.dart';

class _Api extends DeviceApi {
  _Api() : super(Dio());

  int calls = 0;
  DeviceStatusReport report = const DeviceStatusReport(
    control: 'enforce',
    status: 'approved',
    allowed: true,
  );
  final List<String> named = [];
  String? refuseNamesWith;

  @override
  Future<Result<DeviceStatusReport>> me() async {
    calls++;
    return Success(report);
  }

  @override
  Future<Result<DeviceStatusReport>> setName(String name) async {
    named.add(name);
    final refusal = refuseNamesWith;
    if (refusal != null) {
      return FailureResult(
        Failure(message: refusal, errorCode: 'DUPLICATE_DEVICE_NAME'),
      );
    }
    report = DeviceStatusReport(
      control: report.control,
      status: report.status,
      allowed: report.allowed,
      displayName: name,
    );
    return Success(report);
  }
}

class _Session extends ChangeNotifier {
  bool authenticated = false;

  void set(bool value) {
    authenticated = value;
    notifyListeners();
  }
}

Future<(DeviceControl, _Api)> _control({MemoryStorage? storage}) async {
  final api = _Api();
  final control = DeviceControl(
    identity: await loadIdentity(storage: storage),
    access: DeviceAccessController(api: api),
  );
  return (control, api);
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('redirect', () {
    test('never asks anyone to name the phone before sign-in', () async {
      final (control, _) = await _control();

      expect(
        control.redirect(location: '/login', authenticated: false),
        isNull,
      );
    });

    test('sends a signed-in phone the agency has not seen to the naming '
        'step', () async {
      final (control, api) = await _control();
      api.report = const DeviceStatusReport(
        control: 'enforce',
        status: 'pending',
        allowed: false,
        displayName: 'device_a1b2c3d4',
        needsName: true,
      );
      await control.access.refresh();

      // Naming comes before the waiting screen.
      expect(
        control.redirect(location: '/', authenticated: true),
        DeviceRoutes.name,
      );
      expect(
        control.redirect(location: DeviceRoutes.name, authenticated: true),
        isNull,
      );
      expect(control.suggestedName, 'device_a1b2c3d4');
    });

    test('does not ask a phone the agency already knows', () async {
      final (control, api) = await _control();
      api.report = const DeviceStatusReport(
        control: 'enforce',
        status: 'approved',
        allowed: true,
        displayName: 'Van 2',
      );
      await control.access.refresh();

      expect(control.redirect(location: '/', authenticated: true), isNull);
      expect(control.phoneName, 'Van 2');
    });

    test('moves on from the naming step once the name is accepted', () async {
      final (control, api) = await _control();
      api.report = const DeviceStatusReport(
        control: 'enforce',
        status: 'approved',
        allowed: true,
        displayName: 'device_a1b2c3d4',
        needsName: true,
      );
      await control.access.refresh();

      final problem = await control.saveName('  Van 2 ');

      expect(problem, isNull);
      expect(api.named, ['Van 2']);
      expect(
        control.redirect(location: DeviceRoutes.name, authenticated: true),
        '/',
      );
    });

    test('stays on the naming step and shows the agency\'s message when the '
        'name is taken', () async {
      final (control, api) = await _control();
      api.report = const DeviceStatusReport(
        control: 'enforce',
        status: 'approved',
        allowed: true,
        needsName: true,
      );
      await control.access.refresh();
      api.refuseNamesWith =
          "Another phone already has the name 'Van 2'. "
          "Try 'Van 2 2'.";

      final problem = await control.saveName('Van 2');

      expect(problem, contains('Van 2 2'));
      expect(
        control.redirect(location: DeviceRoutes.name, authenticated: true),
        isNull,
      );
    });

    test(
      'shows the waiting screen to a signed-in phone that is waiting',
      () async {
        final (control, _) = await _control(storage: MemoryStorage());
        control.access.reportRefusal('DEVICE_PENDING');

        expect(
          control.redirect(location: '/', authenticated: true),
          DeviceRoutes.waiting,
        );
        expect(
          control.redirect(location: DeviceRoutes.waiting, authenticated: true),
          isNull,
        );
        // Signed out, a waiting phone just goes to sign-in.
        expect(
          control.redirect(location: '/login', authenticated: false),
          isNull,
        );
      },
    );

    test(
      'shows the blocked screen whether or not anyone is signed in',
      () async {
        final (control, _) = await _control(storage: MemoryStorage());
        control.access.reportRefusal('DEVICE_BLOCKED');

        expect(
          control.redirect(location: '/', authenticated: true),
          DeviceRoutes.blocked,
        );
        expect(
          control.redirect(location: '/login', authenticated: false),
          DeviceRoutes.blocked,
        );
        expect(
          control.redirect(
            location: DeviceRoutes.blocked,
            authenticated: false,
          ),
          isNull,
        );
      },
    );

    test('leaves the blocked screen when the user tries again', () async {
      final (control, _) = await _control(storage: MemoryStorage());
      control.access.reportRefusal('DEVICE_BLOCKED');

      control.tryAgain();

      expect(
        control.redirect(location: DeviceRoutes.blocked, authenticated: false),
        '/',
      );
    });

    test('leaves the waiting screen once approved', () async {
      final (control, _) = await _control(storage: MemoryStorage());
      control.access.reportRefusal('DEVICE_PENDING');
      control.access.reset();

      expect(
        control.redirect(location: DeviceRoutes.waiting, authenticated: true),
        '/',
      );
    });
  });

  group('followSession', () {
    test('asks the server when the user signs in', () async {
      final (control, api) = await _control(storage: MemoryStorage());
      final session = _Session();
      control.followSession(
        session: session,
        isAuthenticated: () => session.authenticated,
      );

      session.set(true);
      await Future<void>.delayed(Duration.zero);

      expect(api.calls, 1);
    });

    test('asks at start-up when a session is already restored', () async {
      final (control, api) = await _control(storage: MemoryStorage());
      final session = _Session()..authenticated = true;

      control.followSession(
        session: session,
        isAuthenticated: () => session.authenticated,
      );
      await Future<void>.delayed(Duration.zero);

      expect(api.calls, 1);
    });

    test(
      'forgets the waiting state when the user signs out of a waiting phone',
      () async {
        final (control, _) = await _control(storage: MemoryStorage());
        final session = _Session();
        control.followSession(
          session: session,
          isAuthenticated: () => session.authenticated,
        );
        session.set(true);
        control.access.reportRefusal('DEVICE_PENDING');

        session.set(false);

        expect(control.access.access, DeviceAccess.allowed);
      },
    );

    test('keeps the blocked state after the forced sign-out', () async {
      final (control, _) = await _control(storage: MemoryStorage());
      final session = _Session();
      control.followSession(
        session: session,
        isAuthenticated: () => session.authenticated,
      );
      session.set(true);
      control.access.reportRefusal('DEVICE_BLOCKED');

      session.set(false);

      expect(control.access.access, DeviceAccess.blocked);
    });

    test(
      'asks again when the app returns to the foreground while signed in',
      () async {
        final (control, api) = await _control(storage: MemoryStorage());
        final session = _Session()..authenticated = true;
        control.followSession(
          session: session,
          isAuthenticated: () => session.authenticated,
        );
        await Future<void>.delayed(Duration.zero);
        final before = api.calls;

        control.didChangeAppLifecycleState(AppLifecycleState.resumed);
        await Future<void>.delayed(Duration.zero);

        expect(api.calls, before + 1);
      },
    );

    test('does not ask on resume while signed out', () async {
      final (control, api) = await _control(storage: MemoryStorage());
      final session = _Session();
      control.followSession(
        session: session,
        isAuthenticated: () => session.authenticated,
      );

      control.didChangeAppLifecycleState(AppLifecycleState.resumed);

      expect(api.calls, 0);
    });
  });

  test('setUp plugs the phone into the Dio client', () async {
    final dio = fakeDio((_) => jsonBody({'ok': true}, 200));

    final control = await DeviceControl.setUp(
      dio: dio,
      appType: 'admin_app',
      onBlocked: () async {},
      storage: MemoryStorage(installId: 'install-id-0123456789'),
      detailsSource: () => const FakeDetailsSource(),
    );
    await dio.get<dynamic>('/api/v1/orders');

    expect(control.identity.appType, 'admin_app');
    final sent = (dio.httpClientAdapter as FakeAdapter).seen.single.headers;
    expect(sent['X-Device-Id'], 'install-id-0123456789');
    expect(sent['X-App-Type'], 'admin_app');
  });

  test('signs the user out when the phone is blocked', () async {
    var signedOut = 0;
    final dio = fakeDio((_) => jsonBody({'error_code': 'DEVICE_BLOCKED'}, 403));
    final control = await DeviceControl.setUp(
      dio: dio,
      appType: 'driver_app',
      onBlocked: () async => signedOut++,
      storage: MemoryStorage(installId: 'install-id-0123456789'),
      detailsSource: () => const FakeDetailsSource(),
    );

    await expectLater(
      dio.get<dynamic>('/api/v1/orders'),
      throwsA(isA<DioException>()),
    );

    expect(control.access.access, DeviceAccess.blocked);
    expect(signedOut, 1);
  });
}
