import 'package:core/core.dart';
import 'package:device_identity/device_identity.dart';
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

class _StubApi extends DeviceApi {
  _StubApi(this._results) : super(Dio());

  final List<Result<DeviceStatusReport>> _results;
  int calls = 0;

  @override
  Future<Result<DeviceStatusReport>> me() async => _results[calls++];
}

Result<DeviceStatusReport> _report(String? status, {required bool allowed}) =>
    Success(
      DeviceStatusReport(control: 'enforce', status: status, allowed: allowed),
    );

DeviceAccessController _controller(
  List<Result<DeviceStatusReport>> results, {
  List<String>? log,
}) => DeviceAccessController(
  api: _StubApi(results),
  onBlocked: () async => log?.add('blocked'),
  onResumed: () => log?.add('resumed'),
);

void main() {
  test('starts allowed', () {
    expect(_controller([]).access, DeviceAccess.allowed);
  });

  group('a refusal from any call', () {
    test('DEVICE_PENDING means waiting', () {
      final c = _controller([])..reportRefusal('DEVICE_PENDING');
      expect(c.access, DeviceAccess.pending);
    });

    test('DEVICE_BLOCKED and DEVICE_REMOVED mean blocked', () {
      expect(
        (_controller([])..reportRefusal('DEVICE_BLOCKED')).access,
        DeviceAccess.blocked,
      );
      expect(
        (_controller([])..reportRefusal('DEVICE_REMOVED')).access,
        DeviceAccess.blocked,
      );
    });

    test(
      'DEVICE_REQUIRED changes nothing: the API client refreshes instead',
      () {
        final c = _controller([])..reportRefusal('DEVICE_REQUIRED');
        expect(c.access, DeviceAccess.allowed);
      },
    );

    test('an unknown code changes nothing', () {
      final c = _controller([])..reportRefusal('SOMETHING_ELSE');
      expect(c.access, DeviceAccess.allowed);
    });
  });

  group('asking the server', () {
    test(
      'a waiting phone becomes allowed once approved, and work resumes',
      () async {
        final log = <String>[];
        final c = _controller([
          _report('pending', allowed: false),
          _report('approved', allowed: true),
        ], log: log);

        await c.refresh();
        expect(c.access, DeviceAccess.pending);
        await c.refresh();

        expect(c.access, DeviceAccess.allowed);
        expect(log, ['resumed']);
      },
    );

    test('a blocked phone signs the user out exactly once', () async {
      final log = <String>[];
      final c = _controller([
        _report('blocked', allowed: false),
        _report('blocked', allowed: false),
      ], log: log);

      await c.refresh();
      await c.refresh();

      expect(c.access, DeviceAccess.blocked);
      expect(log, ['blocked']);
    });

    test('a removed phone counts as blocked', () async {
      final c = _controller([_report('removed', allowed: false)]);

      await c.refresh();

      expect(c.access, DeviceAccess.blocked);
    });

    test(
      'an approved or uncontrolled phone stays allowed without a resume',
      () async {
        final log = <String>[];
        final c = _controller([
          _report('approved', allowed: true),
          _report(null, allowed: true),
        ], log: log);

        await c.refresh();
        await c.refresh();

        expect(c.access, DeviceAccess.allowed);
        expect(log, isEmpty);
      },
    );

    test('being offline never locks anyone out', () async {
      final c = _controller([const FailureResult(Failure(message: 'offline'))])
        ..reportRefusal('DEVICE_PENDING');

      await c.refresh();

      expect(c.access, DeviceAccess.pending); // unchanged, not cleared either
      final fresh = _controller([
        const FailureResult(Failure(message: 'offline')),
      ]);
      await fresh.refresh();
      expect(fresh.access, DeviceAccess.allowed);
    });

    test('a refusal code on the check itself is honoured', () async {
      final c = _controller([
        const FailureResult(
          Failure(message: 'no', errorCode: 'DEVICE_BLOCKED'),
        ),
      ]);

      await c.refresh();

      expect(c.access, DeviceAccess.blocked);
    });

    test('does not start a second check while one is running', () async {
      final api = _StubApi([_report('approved', allowed: true)]);
      final c = DeviceAccessController(api: api);

      final first = c.refresh();
      final second = c.refresh();
      await Future.wait([first, second]);

      expect(api.calls, 1);
      expect(c.isChecking, isFalse);
    });

    test('tells listeners when a check starts and ends', () async {
      final c = _controller([_report('approved', allowed: true)]);
      final seen = <bool>[];
      c.addListener(() => seen.add(c.isChecking));

      await c.refresh();

      expect(seen, [true, false]);
    });
  });

  test('reset goes back to allowed, so sign-in can try again', () {
    final c = _controller([])..reportRefusal('DEVICE_BLOCKED');

    c.reset();

    expect(c.access, DeviceAccess.allowed);
  });

  test(
    'a sign-in refusal after reset puts the blocked state straight back',
    () {
      final c = _controller([])
        ..reportRefusal('DEVICE_BLOCKED')
        ..reset()
        ..reportRefusal('DEVICE_BLOCKED');

      expect(c.access, DeviceAccess.blocked);
    },
  );
}
